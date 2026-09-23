# AI Codebase Reviewer & Report Generator

A production-oriented AI platform that ingests codebases, performs multi-agent architectural and security analysis, provides conversational Q&A, and generates structured executive reports with human-in-the-loop review.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn, Pydantic v2, Pydantic-Settings
- **Data & Storage (Local)**: PostgreSQL + `pgvector`, SQLAlchemy (async), Alembic
- **Agent Orchestration**: LangGraph (state graphs with human review gates)
- **Frontend**: Streamlit
- **Packaging & Tooling**: `uv`, `pytest`, `ruff`

---

## 📁 Repository Structure

```
codebase-reviewer/
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git ignore specifications
├── pyproject.toml                # Project dependencies, packaging, and tool settings
├── README.md                     # Project documentation
├── backend/
│   └── app/
│       ├── main.py               # FastAPI application entrypoint, CORS, lifespan
│       ├── core/
│       │   ├── config.py         # Pydantic Settings management
│       │   └── logging.py        # Centralized structured logging
│       ├── api/
│       │   └── v1/
│       │       ├── api.py        # API router aggregator
│       │       └── endpoints/
│       │           └── health.py # Health check endpoints (/health and /api/v1/health)
│       └── schemas/
│           └── health.py         # Pydantic schemas for health responses
├── frontend/
│   ├── app.py                    # Streamlit dashboard checking backend health & API status
│   └── README.md                 # Frontend instructions
├── tests/
│   ├── conftest.py               # Shared pytest fixtures (TestClient)
│   ├── unit/
│   │   ├── test_config.py        # Settings validation & env override tests
│   │   └── test_logging.py       # Logging configuration tests
│   └── integration/
│       └── test_health.py        # Health endpoint integration tests
├── docs/
│   ├── architecture.md           # Modular system architecture & multi-agent workflow
│   └── setup.md                  # Comprehensive developer setup guide
└── scripts/
    ├── run_backend.py            # Development runner for FastAPI backend
    ├── run_frontend.py           # Development runner for Streamlit frontend
    └── run_tests.py              # Test runner script
```

---

## 🚀 Quickstart (Local Environment)

### 1. Prerequisites
- Python 3.11+ (Python 3.12 recommended)
- Astral [`uv`](https://docs.astral.sh/uv/) package manager
- Locally installed PostgreSQL server with the `pgvector` extension:
  ```sql
  CREATE DATABASE codebase_reviewer;
  \c codebase_reviewer
  CREATE EXTENSION IF NOT EXISTS vector;
  ```

### 2. Environment Setup
Install all dependencies and create the virtual environment using `uv`:
```bash
uv sync
```

Copy the environment template:
```bash
cp .env.example .env
```
*(On Windows PowerShell: `Copy-Item .env.example .env`)*

### 3. Run the Backend (FastAPI)
```bash
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
# or
uv run python scripts/run_backend.py
```
- API Health Check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Interactive API Docs: [http://127.0.0.1:8000/api/v1/docs](http://127.0.0.1:8000/api/v1/docs)

### 4. Run the Frontend (Streamlit)
```bash
uv run streamlit run frontend/app.py --server.port 8501
# or
uv run python scripts/run_frontend.py
```
- Web Dashboard: [http://localhost:8501](http://localhost:8501)

### 5. Run Tests
```bash
uv run pytest -v
# or
uv run python scripts/run_tests.py
```

### 6. Linting & Formatting
```bash
uv run ruff check .
uv run ruff format .
```

---

## 🗺️ Architectural Roadmap

- **Phase 1 (Current)**: Repository initialization, FastAPI application, health check, configuration, logging, Streamlit baseline, test suite, and local documentation.
- **Phase 2 (Upcoming)**: Codebase ingestion engine (GitHub cloner, ZIP extractor, Tree-sitter / AST chunking).
- **Phase 3**: PostgreSQL schema, Alembic migrations, and pgvector embeddings storage.
- **Phase 4**: Hybrid retrieval and conversational Q&A engine.
- **Phase 5**: LangGraph multi-agent orchestration (Architecture, Security, Dependencies, Report Synthesizer).
- **Phase 6**: Human-in-the-loop review interface in Streamlit.
- **Phase 7**: Styled PDF and DOCX report generation.
