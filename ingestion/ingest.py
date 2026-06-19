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
# Keys are the exact filename stems (PDF filename minus ".pdf") as downloaded.
# Final approved corpus — 9 papers, all CC BY 4.0 (verified 2026-06-18).
PAPER_METADATA = {
    "jech-2022-219267": {
        "authors": "Igelström, Craig, Lewsey, Lynch, Pearce, Katikireddi",
        "year": "2022",
        "topic": "causal inference overview",
        "citation": "Igelström et al. (2022) Causal inference and effect estimation using observational data. J Epidemiol Community Health."
    },
    "dyw227": {
        "authors": "Daniel, De Stavola, Vansteelandt",
        "year": "2016",
        "topic": "causal inference foundations",
        "citation": "Daniel et al. (2016) Commentary: The formal approach to quantitative causal inference in epidemiology. Int J Epidemiol."
    },
    "dyaa213": {
        "authors": "Tennant, Murray, Arnold, Berrie, Fox, Gadd, Harrison, Keeble, Ranker, Textor, Tomova, Gilthorpe, Ellison",
        "year": "2021",
        "topic": "DAGs confounders",
        "citation": "Tennant et al. (2021) Use of directed acyclic graphs (DAGs) to identify confounders in applied health research. Int J Epidemiol, 50(2):620-632."
    },
    "kwae222": {
        "authors": "Anderson et al.",
        "year": "2024",
        "topic": "target trial emulation",
        "citation": "Anderson et al. (2024) Invited commentary: target trial emulation—a call for more widespread use. Am J Epidemiol."
    },
    "13347_2022_Article_509": {
        "authors": "Broadbent, Grote",
        "year": "2022",
        "topic": "ML causal inference",
        "citation": "Broadbent & Grote (2022) Can Robots Do Epidemiology? Philosophy & Technology, 35(1):14."
    },
    "pme-13-1-1324": {
        "authors": "Boscardin, Sewell, Tolsgaard, Pusic",
        "year": "2024",
        "topic": "p-values",
        "citation": "Boscardin et al. (2024) How to Use and Report on p-values. Perspectives on Medical Education, 13(1):250-254."
    },
    "oeaf070": {
        "authors": "Dyer",
        "year": "2025",
        "topic": "variable selection",
        "citation": "Dyer (2025) Variable selection for causal inference, prediction, and descriptive research. Eur Heart J Open, 5(3):oeaf070."
    },
    "je-35-003": {
        "authors": "Inoue, Sakamaki, Komukai, Ito, Goto, Shinozaki",
        "year": "2025",
        "topic": "confounder selection sensitivity analysis",
        "citation": "Inoue et al. (2025) Methodological Tutorial Series for Epidemiological Studies: Confounder Selection and Sensitivity Analyses. J Epidemiol, 35(1):3-10."
    },
    "10.1177_09622802231181230": {
        "authors": "Penning de Vries, Groenwold",
        "year": "2023",
        "topic": "negative controls",
        "citation": "Penning de Vries & Groenwold (2023) Negative controls: Concepts and caveats. Statistical Methods in Medical Research, 32(8):1576-1587."
    },
}


def extract_text_from_pdf(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
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

    unmatched = [p.stem for p in pdf_files if p.stem not in PAPER_METADATA]
    if unmatched:
        print(f"\nWARNING: {len(unmatched)} file(s) have no exact metadata match "
              f"(will fall back to fuzzy/Unknown): {unmatched}")

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

        try:
            text = extract_text_from_pdf(pdf_path)
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