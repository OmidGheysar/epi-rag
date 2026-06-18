"""
EpiRAG — Knowledge Base Ingestion Script
Extracts text from PDFs, chunks, embeds, and loads into ChromaDB.

Usage:
    python ingestion/ingest.py

Run once to build the knowledge base. Re-run if you add new papers.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb

# --- Load environment ---
load_dotenv()

# --- Config ---
PAPERS_DIR = Path("data/papers")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "data/chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "epi_methodology")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 150))

# --- Paper metadata ---
# Maps filename stem to metadata for citation and filtering
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
    "Negative Controls A Tool for Detecting Confou": {
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
    "The distinction between causal, predictive, and": {
        "authors": "Dyer",
        "year": "2025",
        "topic": "causal predictive descriptive mistakes",
        "citation": "Dyer (2025) The distinction between causal, predictive, and descriptive research"
    },
    "Using Big Data to Emulate a Target Trial When a": {
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

# --- Hernan book: only ingest these chapters (Part I) ---
HERNAN_BOOK_CHAPTERS = {
    "Causal inference what if Hernan": {
        "pages": list(range(0, 160)),  # Part I: Ch 1-10, ~pages 1-160
        "note": "Part I only — foundations, DAGs, confounding, selection bias"
    }
}


def extract_text_from_pdf(pdf_path: Path, page_range: list = None) -> str:
    """Extract text from a PDF, optionally restricting to a page range."""
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
    """Match filename stem to metadata, with fuzzy prefix matching."""
    # Exact match first
    if filename_stem in PAPER_METADATA:
        return PAPER_METADATA[filename_stem]
    # Prefix match for truncated filenames
    for key, meta in PAPER_METADATA.items():
        if filename_stem.startswith(key[:30]) or key.startswith(filename_stem[:30]):
            return meta
    # Fallback
    return {
        "authors": "Unknown",
        "year": "Unknown",
        "topic": "epidemiology methodology",
        "citation": filename_stem
    }


def ingest():
    print("=" * 55)
    print("  EpiRAG — Knowledge Base Ingestion")
    print("=" * 55)

    # --- Check papers directory ---
    if not PAPERS_DIR.exists():
        print(f"\nERROR: Papers directory not found: {PAPERS_DIR}")
        print("Make sure you are running from the project root.")
        sys.exit(1)

    pdf_files = list(PAPERS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"\nERROR: No PDF files found in {PAPERS_DIR}")
        sys.exit(1)

    print(f"\nFound {len(pdf_files)} PDF files in {PAPERS_DIR}")

    # --- Initialize text splitter ---
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    # --- Initialize embeddings ---
    print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    print("Embedding model loaded.")

    # --- Initialize ChromaDB ---
    print(f"\nConnecting to ChromaDB at: {CHROMA_DB_PATH}")
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # Delete existing collection to rebuild fresh
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"Deleted existing collection: {COLLECTION_NAME}")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )
    print(f"Created collection: {COLLECTION_NAME}")

    # --- Process each PDF ---
    total_chunks = 0

    for pdf_path in sorted(pdf_files):
        stem = pdf_path.stem
        print(f"\nProcessing: {pdf_path.name}")

        # Get page range for book chapters
        page_range = None
        if stem in HERNAN_BOOK_CHAPTERS:
            page_range = HERNAN_BOOK_CHAPTERS[stem]["pages"]
            print(f"  → Book detected: ingesting Part I only ({len(page_range)} pages)")

        # Extract text
        try:
            text = extract_text_from_pdf(pdf_path, page_range)
        except Exception as e:
            print(f"  ERROR extracting text: {e}")
            continue

        if not text.strip():
            print(f"  WARNING: No text extracted — skipping")
            continue

        print(f"  Extracted {len(text):,} characters")

        # Chunk
        chunks = splitter.split_text(text)
        print(f"  Created {len(chunks)} chunks")

        # Get metadata
        meta = get_metadata_for_file(stem)

        # Embed and add to ChromaDB
        chunk_ids = []
        chunk_texts = []
        chunk_metadatas = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{stem}_{i:04d}"
            chunk_ids.append(chunk_id)
            chunk_texts.append(chunk)
            chunk_metadatas.append({
                "source": pdf_path.name,
                "authors": meta["authors"],
                "year": meta["year"],
                "topic": meta["topic"],
                "citation": meta["citation"],
                "chunk_index": i,
                "total_chunks": len(chunks)
            })

        # Batch embed and add
        batch_size = 50
        for start in range(0, len(chunks), batch_size):
            end = min(start + batch_size, len(chunks))
            batch_texts = chunk_texts[start:end]
            batch_ids = chunk_ids[start:end]
            batch_metas = chunk_metadatas[start:end]

            batch_embeddings = embeddings.embed_documents(batch_texts)

            collection.add(
                ids=batch_ids,
                embeddings=batch_embeddings,
                documents=batch_texts,
                metadatas=batch_metas
            )

        total_chunks += len(chunks)
        print(f"  ✓ Added {len(chunks)} chunks to ChromaDB")

    # --- Summary ---
    print("\n" + "=" * 55)
    print(f"  Ingestion complete.")
    print(f"  Total chunks: {total_chunks:,}")
    print(f"  Collection: {COLLECTION_NAME}")
    print(f"  ChromaDB path: {CHROMA_DB_PATH}")
    print("=" * 55)

    # --- Quick retrieval test ---
    print("\nRunning quick retrieval test...")
    test_query = "What is the difference between causal and predictive research?"
    test_embedding = embeddings.embed_query(test_query)
    results = collection.query(
        query_embeddings=[test_embedding],
        n_results=3
    )
    print(f"Query: '{test_query}'")
    print("Top 3 results:")
    for i, (doc, meta) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0]
    )):
        print(f"\n  [{i+1}] {meta['citation']}")
        print(f"       {doc[:150].strip()}...")

    print("\nKnowledge base is ready.")


if __name__ == "__main__":
    ingest()