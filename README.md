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

Add the following to `.env`:

```
OPENAI_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=epi-methodology
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LLM_MODEL=gpt-4o-mini
TOP_K=5
```

Then copy your PDFs into `data/papers/`.

## Ingest

```bash
python ingestion/ingest.py
```

## Run

```bash
uvicorn app.main:app --reload
streamlit run frontend/streamlit_app.py
```

## Sources & License

EpiRAG retrieves and synthesizes from a corpus of 9 papers on epidemiological
methodology — causal inference, confounder selection, target trial emulation,
variable selection, p-value interpretation, and negative controls. All sources
are **CC BY 4.0** licensed (verified individually via the explicit license
statement on each article page).

| Paper | Topic |
|---|---|
| Igelström et al. (2022) | Causal inference & effect estimation overview |
| Daniel, De Stavola & Vansteelandt (2016) | Causal inference foundations |
| Tennant et al. (2021) | DAGs & confounders |
| Anderson et al. (2024) | Target trial emulation |
| Broadbent & Grote (2022) | ML & causal inference |
| Boscardin et al. (2024) | p-values |
| Dyer (2025) | Variable selection |
| Inoue et al. (2025) | Confounder selection & sensitivity analysis |
| Penning de Vries & Groenwold (2023) | Negative controls |

EpiRAG is a non-commercial educational/research tool. It does not run
statistical analyses or access user data, and should not be treated as a
substitute for expert methodological consultation.

## Technical Writeup
For the full engineering retrospective (architecture decisions, evaluation results, what I'd do differently), see [WRITEUP.md](WRITEUP.md).