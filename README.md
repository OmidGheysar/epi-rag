# EpiRAG — Epidemiological Methodology Assistant

A retrieval-augmented reasoning system over canonical epidemiological methodology
literature. Helps junior researchers and non-statisticians critically evaluate
their observational analyses.

## Setup

```bash
setup.bat
venv\Scripts\activate
pip install -r requirements.txt
```

Add your OpenAI API key to `.env`, then copy your PDFs into `data/papers/`.

## Ingest

```bash
python ingestion/ingest.py
```

## Run

```bash
uvicorn app.main:app --reload
streamlit run frontend/streamlit_app.py
```
