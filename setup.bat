@echo off
REM EpiRAG Project Setup Script for Windows
REM Run this once in an empty folder: setup.bat

echo ================================================
echo   EpiRAG — Project Setup (Windows)
echo ================================================

REM --- Create directory structure ---
echo.
echo Creating project structure...

mkdir app
mkdir frontend
mkdir ingestion
mkdir data\papers
mkdir data\chroma_db
mkdir evaluation
mkdir tests

REM --- Create empty Python files ---
echo Creating empty Python files...

REM App
type nul > app\__init__.py
type nul > app\main.py
type nul > app\pipeline.py
type nul > app\retriever.py

REM Frontend
type nul > frontend\__init__.py
type nul > frontend\streamlit_app.py

REM Ingestion
type nul > ingestion\__init__.py
type nul > ingestion\ingest.py
type nul > ingestion\preprocess.py

REM Evaluation
type nul > evaluation\__init__.py
type nul > evaluation\gold_standard.py
type nul > evaluation\evaluate.py

REM Tests
type nul > tests\__init__.py
type nul > tests\test_retrieval.py
type nul > tests\test_pipeline.py

REM --- Create .env template ---
echo Creating .env template...
(
echo # OpenAI
echo OPENAI_API_KEY=your_openai_api_key_here
echo.
echo # Embedding model ^(HuggingFace — no key needed for local^)
echo EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
echo.
echo # LLM model
echo LLM_MODEL=gpt-4o-mini
echo.
echo # ChromaDB
echo CHROMA_DB_PATH=data/chroma_db
echo CHROMA_COLLECTION_NAME=epi_methodology
echo.
echo # Chunking
echo CHUNK_SIZE=800
echo CHUNK_OVERLAP=150
echo.
echo # Retrieval
echo TOP_K=5
echo.
echo # App
echo APP_TITLE=EpiRAG — Epidemiological Methodology Assistant
echo APP_ENV=development
) > .env

REM --- Create .gitignore ---
echo Creating .gitignore...
(
echo # Environment
echo .env
echo .env.local
echo .env.production
echo.
echo # Virtual environment
echo venv/
echo .venv/
echo env/
echo.
echo # Vector store — rebuild from papers
echo data/chroma_db/
echo.
echo # Python
echo __pycache__/
echo *.py[cod]
echo *.pyo
echo *.pyd
echo *.egg-info/
echo dist/
echo build/
echo.
echo # OS
echo .DS_Store
echo Thumbs.db
echo.
echo # IDE
echo .vscode/settings.json
echo .idea/
echo.
echo # Logs
echo *.log
echo logs/
echo.
echo # Model cache
echo .cache/
echo models/
echo.
echo # Streamlit secrets
echo .streamlit/secrets.toml
) > .gitignore

REM --- Create requirements.txt ---
echo Creating requirements.txt...
(
echo # Core RAG stack
echo langchain==0.3.7
echo langchain-community==0.3.7
echo langchain-huggingface==0.1.2
echo langchain-openai==0.2.9
echo langgraph==0.2.45
echo.
echo # Vector store
echo chromadb==0.5.18
echo.
echo # PDF processing
echo pypdf==5.1.0
echo.
echo # Embeddings
echo sentence-transformers==3.3.1
echo.
echo # API backend
echo fastapi==0.115.5
echo uvicorn==0.32.1
echo.
echo # Frontend
echo streamlit==1.40.1
echo.
echo # Evaluation
echo ragas==0.2.6
echo.
echo # Utilities
echo python-dotenv==1.0.1
echo pydantic==2.10.1
) > requirements.txt

REM --- Create README ---
echo Creating README.md...
(
echo # EpiRAG — Epidemiological Methodology Assistant
echo.
echo A retrieval-augmented reasoning system over canonical epidemiological methodology
echo literature. Helps junior researchers and non-statisticians critically evaluate
echo their observational analyses.
echo.
echo ## Setup
echo.
echo ```bash
echo setup.bat
echo venv\Scripts\activate
echo pip install -r requirements.txt
echo ```
echo.
echo Add your OpenAI API key to `.env`, then copy your PDFs into `data/papers/`.
echo.
echo ## Ingest
echo.
echo ```bash
echo python ingestion/ingest.py
echo ```
echo.
echo ## Run
echo.
echo ```bash
echo uvicorn app.main:app --reload
echo streamlit run frontend/streamlit_app.py
echo ```
) > README.md

REM --- Create virtual environment ---
echo.
echo Creating virtual environment...
python -m venv venv
echo Virtual environment created at .\venv

REM --- Done ---
echo.
echo ================================================
echo   Setup complete. Next steps:
echo.
echo   1. Activate venv:
echo      venv\Scripts\activate
echo.
echo   2. Install dependencies:
echo      pip install -r requirements.txt
echo.
echo   3. Add your OpenAI key to .env
echo.
echo   4. Copy your 9 PDFs into data\papers\
echo.
echo   5. Run ingestion:
echo      python ingestion\ingest.py
echo ================================================
pause
