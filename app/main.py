"""
EpiRAG — FastAPI Backend
Exposes the LangGraph pipeline as a REST API.

Endpoints:
    POST /ask       — main question answering endpoint
    GET  /health    — health check
    GET  /info      — knowledge base info

Usage:
    uvicorn app.main:app --reload
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from app.pipeline import run_pipeline

load_dotenv()

# --- App ---
app = FastAPI(
    title="EpiRAG — Epidemiological Methodology Assistant",
    description="""
    A retrieval-augmented reasoning system over canonical epidemiological 
    methodology literature. Helps junior researchers critically evaluate 
    their observational analyses.
    """,
    version="0.1.0"
)

# --- CORS (allow Streamlit frontend) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request / Response models ---
class QuestionRequest(BaseModel):
    question: str

    class Config:
        json_schema_extra = {
            "example": {
                "question": "Is my study causal or descriptive if I am looking at the association between smoking and lung cancer?"
            }
        }


class RetrievedChunk(BaseModel):
    text: str
    citation: str
    authors: str
    year: str
    topic: str
    relevance_score: float


class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: List[str]
    retrieved_chunks: List[RetrievedChunk]
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class InfoResponse(BaseModel):
    title: str
    version: str
    embedding_model: str
    llm_model: str
    collection_name: str
    top_k: int
    papers: List[str]


# --- Knowledge base papers list ---
PAPERS = [
    "Hernán & Robins (2020) Causal Inference: What If — Part I",
    "Greenland, Pearl & Robins (1999) Causal Diagrams for Epidemiologic Research",
    "Hernán, Hsu & Healy (2019) A Second Chance to Get Causal Inference Right",
    "Dyer (2025) The Distinction Between Causal, Predictive, and Descriptive Research",
    "Dyer (2025) Variable Selection for Causal Inference",
    "Kaufman (2017) Statistics, Adjusted Statistics, and Maladjusted Statistics",
    "Hernán & Robins (2016) Using Big Data to Emulate a Target Trial",
    "Lipsitch, Tchetgen & Cohen (2010) Negative Controls",
    "VanderWeele (2017) Outcome-Wide Epidemiology",
    "VanderWeele, Mathur & Chen (2020) Outcome-Wide Longitudinal Designs",
    "Fox et al. (2022) A Framework for Descriptive Epidemiology",
]


# --- Endpoints ---
@app.get("/health", response_model=HealthResponse)
def health_check():
    """Check if the API is running."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.utcnow().isoformat()
    )


@app.get("/info", response_model=InfoResponse)
def get_info():
    """Return knowledge base and model configuration."""
    return InfoResponse(
        title="EpiRAG — Epidemiological Methodology Assistant",
        version="0.1.0",
        embedding_model=os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        collection_name=os.getenv("CHROMA_COLLECTION_NAME", "epi_methodology"),
        top_k=int(os.getenv("TOP_K", 5)),
        papers=PAPERS
    )


@app.post("/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest):
    """
    Submit a methodological question about your observational study.

    The system retrieves relevant passages from canonical epidemiological
    methodology literature and synthesizes a grounded answer with citations.
    """
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if len(question) < 10:
        raise HTTPException(status_code=400, detail="Question is too short. Please provide more detail.")

    if len(question) > 2000:
        raise HTTPException(status_code=400, detail="Question is too long. Please keep it under 2000 characters.")

    try:
        result = run_pipeline(question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    # Format retrieved chunks
    chunks = [
        RetrievedChunk(
            text=chunk["text"],
            citation=chunk["citation"],
            authors=chunk["authors"],
            year=chunk["year"],
            topic=chunk["topic"],
            relevance_score=chunk["relevance_score"]
        )
        for chunk in result["retrieved_chunks"]
    ]

    return AnswerResponse(
        question=result["question"],
        answer=result["answer"],
        sources=result["sources"],
        retrieved_chunks=chunks,
        timestamp=datetime.utcnow().isoformat()
    )


# --- Run directly ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)