"""
EpiRAG — LangGraph Pipeline
Two-node pipeline:
  Node 1: retrieve — fetch relevant chunks from ChromaDB
  Node 2: synthesize — generate grounded answer using LLM

Usage:
    from app.pipeline import run_pipeline
    result = run_pipeline("Is my study causal or descriptive?")
"""

import os
from typing import TypedDict, List
from dotenv import load_dotenv

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

load_dotenv()

# --- Config ---
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "data/chroma_db")
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "epi_methodology")
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
1. Base your answer ONLY on the retrieved passages provided. Do not add claims from outside these passages.
2. Always cite the source of each key point using the citation provided in the context.
3. If the retrieved passages do not contain enough information to answer the question, say so clearly.
4. Do not run statistical analyses or access the researcher's data.
5. Identify specific gaps or problems in the researcher's reasoning when relevant.
6. Keep answers clear and accessible — avoid unnecessary jargon.
7. Always show the source passages you used at the end of your answer.

Your goal is to help the researcher understand what their study design can and cannot support, 
grounded in the epidemiological methodology literature."""


# --- Pipeline state ---
class PipelineState(TypedDict):
    question: str
    retrieved_chunks: List[dict]
    answer: str
    sources: List[str]


# --- Initialize clients (lazy loaded) ---
_embeddings = None
_collection = None
_llm = None


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embeddings


def get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = client.get_collection(COLLECTION_NAME)
    return _collection


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
    """Retrieve relevant chunks from ChromaDB."""
    question = state["question"]

    embeddings = get_embeddings()
    collection = get_collection()

    query_embedding = embeddings.embed_query(question)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=TOP_K,
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        chunks.append({
            "text": doc,
            "citation": meta.get("citation", "Unknown"),
            "authors": meta.get("authors", "Unknown"),
            "year": meta.get("year", "Unknown"),
            "topic": meta.get("topic", ""),
            "relevance_score": round(1 - dist, 3)
        })

    return {**state, "retrieved_chunks": chunks}


# --- Node 2: Synthesize ---
def synthesize(state: PipelineState) -> PipelineState:
    """Synthesize a grounded answer from retrieved chunks."""
    question = state["question"]
    chunks = state["retrieved_chunks"]

    if not chunks:
        return {
            **state,
            "answer": "I could not find relevant passages in the methodology literature to answer this question.",
            "sources": []
        }

    # Build context from retrieved chunks
    context_parts = []
    for i, chunk in enumerate(chunks):
        context_parts.append(
            f"[Source {i+1}] {chunk['citation']}\n"
            f"Relevance: {chunk['relevance_score']}\n"
            f"---\n{chunk['text']}\n"
        )
    context = "\n\n".join(context_parts)

    # Build user message
    user_message = f"""Question from researcher:
{question}

Retrieved passages from the epidemiological methodology literature:

{context}

Based strictly on these passages, provide a methodologically grounded answer. 
Identify any gaps in the researcher's approach if relevant.
Cite sources by their [Source N] label and full citation.
End your answer with a 'Sources Used' section listing the citations."""

    llm = get_llm()
    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message)
    ])

    # Extract unique sources
    sources = list({chunk["citation"] for chunk in chunks})

    return {
        **state,
        "answer": response.content,
        "sources": sources
    }


# --- Build LangGraph pipeline ---
def build_pipeline():
    graph = StateGraph(PipelineState)

    graph.add_node("retrieve", retrieve)
    graph.add_node("synthesize", synthesize)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


# --- Public interface ---
_pipeline = None


def run_pipeline(question: str) -> dict:
    """
    Run the full RAG pipeline on a question.

    Returns:
        dict with keys:
            - question: the original question
            - answer: synthesized answer grounded in literature
            - sources: list of citation strings used
            - retrieved_chunks: raw retrieved passages
    """
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
        "Is my study causal or descriptive if I am looking at association between smoking and lung cancer in a cohort?",
        "What does a p-value actually tell me about my results?",
        "Should I adjust for all variables that are correlated with my outcome?"
    ]

    print("=" * 55)
    print("  EpiRAG — Pipeline Test")
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