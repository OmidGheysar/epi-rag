"""
EpiRAG — Pinecone Ingestion Script
Extracts text from PDFs, chunks, embeds, and uploads to Pinecone.

Usage:
    python ingestion/ingest.py

Run once to build the knowledge base. Re-run if you add new papers.
"""

import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone import Pinecone

# --- Load environment ---
load_dotenv()

# --- Config ---
PAPERS_DIR = Path("data/papers")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "epi-methodology")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 150))

# --- Paper metadata ---
PAPER_METADATA = {
    "A Framework for Descriptive Epidemiology": {
        "authors": "Fox et al.",
        "year": "2022",
        "topic": "descriptive epidemiology",
        "citation": "Fox et al. (2022) A Framework for Descriptive Epidemiology"
    },
    "A Second Chance to Get Causal Inference Right A": {
        "authors": "Hernán, Hsu & Healy",
        "year": "2019",
        "topic": "causal inference classification",
        "citation": "Hernán, Hsu & Healy (2019) A Second Chance to Get Causal Inference Right"
    },
    "Causal Diagrams for Epidemiologic Research": {
        "authors": "Greenland, Pearl & Robins",
        "year": "1999",
        "topic": "DAGs confounding",
        "citation": "Greenland, Pearl & Robins (1999) Causal Diagrams for Epidemiologic Research"
    },
    "Causal inference what if Hernan": {
        "authors": "Hernán & Robins",
        "year": "2020",
        "topic": "causal inference foundations",
        "citation": "Hernán & Robins (2020) Causal Inference: What If"
    },
    "kaufman2017": {
        "authors": "Kaufman",
        "year": "2017",
        "topic": "statistical adjustment confounding",
        "citation": "Kaufman (2017) Statistics, Adjusted Statistics, and Maladjusted Statistics"
    },
    "Negative Controls A Tool for Detecting Confounding and Bias in Observational Studies": {
        "authors": "Lipsitch, Tchetgen & Cohen",
        "year": "2010",
        "topic": "negative controls bias detection",
        "citation": "Lipsitch, Tchetgen & Cohen (2010) Negative Controls"
    },
    "outcome_wide_epidemiology.15": {
        "authors": "VanderWeele",
        "year": "2017",
        "topic": "outcome-wide epidemiology",
        "citation": "VanderWeele (2017) Outcome-Wide Epidemiology"
    },
    "OutcomeWide_StatisticalScience": {
        "authors": "VanderWeele, Mathur & Chen",
        "year": "2020",
        "topic": "outcome-wide longitudinal designs",
        "citation": "VanderWeele, Mathur & Chen (2020) Outcome-Wide Longitudinal Designs"
    },
    "The distinction between causal, predictive, and descriptive": {
        "authors": "Dyer",
        "year": "2025",
        "topic": "causal predictive descriptive mistakes",
        "citation": "Dyer (2025) The distinction between causal, predictive, and descriptive research"
    },
    "Using Big Data to Emulate a Target Trial When a Randomized Trial Is Not Available": {
        "authors": "Hernán & Robins",
        "year": "2016",
        "topic": "target trial emulation",
        "citation": "Hernán & Robins (2016) Using Big Data to Emulate a Target Trial"
    },
    "Variable selection for causal inference": {
        "authors": "Dyer",
        "year": "2025",
        "topic": "variable selection confounding",
        "citation": "Dyer (2025) Variable Selection for Causal Inference"
    },
}

HERNAN_BOOK_PAGES = list(range(0, 160))


def extract_text_from_pdf(pdf_path: Path, page_range: list = None) -> str:
    reader = PdfReader(str(pdf_path))
    pages = page_range if page_range else range(len(reader.pages))
    text = ""
    for i in pages:
        if i < len(reader.pages):
            page_text = reader.pages[i].extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def get_metadata_for_file(filename_stem: str) -> dict:
    if filename_stem in PAPER_METADATA:
        return PAPER_METADATA[filename_stem]
    for key, meta in PAPER_METADATA.items():
        if filename_stem.startswith(key[:30]) or key.startswith(filename_stem[:30]):
            return meta
    return {
        "authors": "Unknown",
        "year": "Unknown",
        "topic": "epidemiology methodology",
        "citation": filename_stem
    }


def sanitize_id(text: str) -> str:
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', text)
    return safe[:512]


def ingest():
    print("=" * 55)
    print("  EpiRAG — Pinecone Ingestion")
    print("=" * 55)

    if not PINECONE_API_KEY:
        print("\nERROR: PINECONE_API_KEY not found in .env")
        sys.exit(1)

    if not PAPERS_DIR.exists():
        print(f"\nERROR: Papers directory not found: {PAPERS_DIR}")
        sys.exit(1)

    pdf_files = list(PAPERS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"\nERROR: No PDF files found in {PAPERS_DIR}")
        sys.exit(1)

    print(f"\nFound {len(pdf_files)} PDF files")

    # --- Initialize Pinecone ---
    print(f"\nConnecting to Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)
    print(f"Connected to index: {PINECONE_INDEX_NAME}")

    # --- Initialize embeddings ---
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    print("Embedding model loaded.")

    # --- Initialize text splitter ---
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    total_chunks = 0

    for pdf_path in sorted(pdf_files):
        stem = pdf_path.stem
        print(f"\nProcessing: {pdf_path.name}")

        page_range = None
        if "Causal inference what if Hernan" in stem:
            page_range = HERNAN_BOOK_PAGES
            print(f"  Book: ingesting Part I only ({len(page_range)} pages)")

        try:
            text = extract_text_from_pdf(pdf_path, page_range)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        if not text.strip():
            print(f"  WARNING: No text extracted — skipping")
            continue

        print(f"  Extracted {len(text):,} characters")

        chunks = splitter.split_text(text)
        print(f"  Created {len(chunks)} chunks")

        meta = get_metadata_for_file(stem)

        batch_size = 50
        for start in range(0, len(chunks), batch_size):
            end = min(start + batch_size, len(chunks))
            batch_chunks = chunks[start:end]
            batch_embeddings = embeddings.embed_documents(batch_chunks)

            vectors = []
            for i, (chunk, embedding) in enumerate(zip(batch_chunks, batch_embeddings)):
                chunk_index = start + i
                vector_id = sanitize_id(f"{stem}_{chunk_index:04d}")
                vectors.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": {
                        "text": chunk,
                        "source": pdf_path.name,
                        "authors": meta["authors"],
                        "year": meta["year"],
                        "topic": meta["topic"],
                        "citation": meta["citation"],
                        "chunk_index": chunk_index,
                        "total_chunks": len(chunks)
                    }
                })

            index.upsert(vectors=vectors)

        total_chunks += len(chunks)
        print(f"  ✓ Uploaded {len(chunks)} chunks to Pinecone")

    print("\n" + "=" * 55)
    print(f"  Ingestion complete.")
    print(f"  Total chunks: {total_chunks:,}")
    print(f"  Pinecone index: {PINECONE_INDEX_NAME}")
    print("=" * 55)

    # --- Quick test ---
    print("\nRunning retrieval test...")
    test_query = "What is the difference between causal and predictive research?"
    test_embedding = embeddings.embed_query(test_query)
    results = index.query(vector=test_embedding, top_k=3, include_metadata=True)

    print(f"Query: '{test_query}'")
    for i, match in enumerate(results["matches"]):
        citation = match["metadata"].get("citation", "Unknown")
        preview = match["metadata"].get("text", "")[:150]
        score = round(match["score"], 3)
        print(f"\n  [{i+1}] {citation} (score: {score})")
        print(f"       {preview}...")

    print("\nKnowledge base is ready in Pinecone.")


if __name__ == "__main__":
    ingest()