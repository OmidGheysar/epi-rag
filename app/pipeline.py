"""
EpiRAG — LangGraph Pipeline (Pinecone version)
Two-node pipeline:
  Node 1: retrieve — fetch relevant chunks from Pinecone
  Node 2: synthesize — generate grounded answer using LLM

Usage:
    from app.pipeline import run_pipeline
    result = run_pipeline("Is my study causal or descriptive?")
"""

import os
import sys
from typing import TypedDict, List
from pathlib import Path
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from pinecone import Pinecone

sys.path.append(str(Path(__file__).parent.parent))
load_dotenv()

# --- Config ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "epi-methodology")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
TOP_K = int(os.getenv("TOP_K", 5))

# --- System prompt ---
SYSTEM_PROMPT = """You are an epidemiological methodology advisor. Your role is to help 
junior researchers and non-statisticians critically evaluate their observational studies.

You answer questions about:
- Study design classification (causal, predictive, or descriptive)
- Interpretation of statistical results including p-values
- Confounding, adjustment, and DAG-based reasoning
- When causal claims are and are not supported
- Common methodological mistakes in observational research
- Variable selection and adjustment strategies

STRICT RULES:
1. Base your answer ONLY on the retrieved passages provided.
2. Always cite the source of each key point using the citation provided.
3. If retrieved passages do not contain enough information, say so clearly.
4. Do not run statistical analyses or access the researcher's data.
5. Identify specific gaps or problems in the researcher's reasoning when relevant.
6. Keep answers clear and accessible — avoid unnecessary jargon.
7. In the Sources Used section, list each source only once even if used multiple times."""


# --- Pipeline state ---
class PipelineState(TypedDict):
    question: str
    retrieved_chunks: List[dict]
    answer: str
    sources: List[str]


# --- Lazy loaded clients ---
_embeddings = None
_index = None
_llm = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings


def get_index():
    global _index
    if _index is None:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        _index = pc.Index(PINECONE_INDEX_NAME)
    return _index


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=LLM_MODEL,
            temperature=0.1,
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
    return _llm


# --- Node 1: Retrieve ---
def retrieve(state: PipelineState) -> PipelineState:
    question = state["question"]

    embeddings = get_embeddings()
    index = get_index()

    query_embedding = embeddings.embed_query(question)

    results = index.query(
        vector=query_embedding,
        top_k=TOP_K,
        include_metadata=True
    )

    chunks = []
    for match in results["matches"]:
        meta = match.get("metadata", {})
        chunks.append({
            "text": meta.get("text", ""),
            "citation": meta.get("citation", "Unknown"),
            "authors": meta.get("authors", "Unknown"),
            "year": meta.get("year", "Unknown"),
            "topic": meta.get("topic", ""),
            "relevance_score": round(match["score"], 3)
        })

    return {**state, "retrieved_chunks": chunks}


# --- Node 2: Synthesize ---
def synthesize(state: PipelineState) -> PipelineState:
    question = state["question"]
    chunks = state["retrieved_chunks"]

    if not chunks:
        return {
            **state,
            "answer": "I could not find relevant passages to answer this question.",
            "sources": []
        }

    # Build unique citation map
    unique_citations = {}
    source_number = 1
    for chunk in chunks:
        citation = chunk["citation"]
        if citation not in unique_citations:
            unique_citations[citation] = source_number
            source_number += 1

    # Build context with deduplicated source numbers
    context_parts = []
    for chunk in chunks:
        source_num = unique_citations[chunk["citation"]]
        context_parts.append(
            f"[Source {source_num}] {chunk['citation']}\n"
            f"---\n{chunk['text']}\n"
        )
    context = "\n\n".join(context_parts)

    sources_legend = "\n".join(
        f"[Source {num}] {citation}"
        for citation, num in unique_citations.items()
    )

    user_message = (
        f"Question from researcher:\n{question}\n\n"
        f"Retrieved passages:\n\n{context}\n\n"
        f"Source legend (list each ONCE only in Sources Used):\n{sources_legend}\n\n"
        f"Provide a grounded answer. Cite inline with [Source N]. "
        f"End with Sources Used listing each source ONCE."
    )

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ])

    # Deduplicated sources preserving order
    seen = set()
    sources = []
    for chunk in chunks:
        citation = chunk["citation"]
        if citation not in seen:
            seen.add(citation)
            sources.append(citation)

    return {
        **state,
        "answer": response.content,
        "sources": sources
    }


# --- Build pipeline ---
def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("synthesize", synthesize)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "synthesize")
    graph.add_edge("synthesize", END)
    return graph.compile()


_pipeline = None


def run_pipeline(question: str) -> dict:
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()

    result = _pipeline.invoke({
        "question": question,
        "retrieved_chunks": [],
        "answer": "",
        "sources": []
    })

    return {
        "question": result["question"],
        "answer": result["answer"],
        "sources": result["sources"],
        "retrieved_chunks": result["retrieved_chunks"]
    }


# --- Quick test ---
if __name__ == "__main__":
    test_questions = [
        "Is my study causal or descriptive if I am looking at association between smoking and lung cancer?",
        "What does a p-value actually tell me about my results?",
        "Should I adjust for all variables that are correlated with my outcome?"
    ]

    print("=" * 55)
    print("  EpiRAG — Pipeline Test (Pinecone)")
    print("=" * 55)

    for question in test_questions:
        print(f"\nQ: {question}")
        print("-" * 55)
        result = run_pipeline(question)
        print(result["answer"])
        print("\nSources:")
        for s in result["sources"]:
            print(f"  - {s}")
        print("=" * 55)