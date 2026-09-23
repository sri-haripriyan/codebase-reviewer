# Local Developer Setup Guide

This guide describes how to configure, run, and test the **AI Codebase Reviewer** on your local machine using `uv` and a local PostgreSQL instance.

---

## 1. Prerequisites

- **Python**: 3.11+ (Python 3.12 recommended)
- **uv**: Modern, high-speed Python package manager ([Astral uv](https://docs.astral.sh/uv/))
- **PostgreSQL**: Locally installed PostgreSQL 15+ with the `pgvector` extension.

---

## 2. Setting Up Local PostgreSQL with pgvector

Ensure your local PostgreSQL server is running. Open your PostgreSQL terminal (`psql` or pgAdmin) and run:

```sql
-- 1. Create database
CREATE DATABASE codebase_reviewer;

-- 2. Connect to the database
\c codebase_reviewer

-- 3. Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 4. Verify extension installation
SELECT * FROM pg_extension WHERE extname = 'vector';
```

---

## 3. Environment Setup with `uv`

1. **Clone or Navigate to the Repository**:
   ```bash
   cd d:/projects/codebase-reviewer
   ```

2. **Create and Synchronize the Virtual Environment**:
   `uv` will automatically create the virtual environment and install all dependencies:
   ```bash
   uv sync
   ```

3. **Configure Environment Variables**:
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to verify your local database credentials (e.g. `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT`).

---

## 4. Running the Applications

### A. Run the FastAPI Backend

You can use the helper script or launch directly with `uv`:

```bash
# Direct command
uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Or using the runner script
uv run python scripts/run_backend.py
```

- API Base URL: `http://127.0.0.1:8000`
- Interactive Swagger Docs: `http://127.0.0.1:8000/api/v1/docs`
- Health Check: `http://127.0.0.1:8000/health` or `http://127.0.0.1:8000/api/v1/health`

### B. Run the Streamlit Frontend

In a separate terminal:

```bash
# Direct command
uv run streamlit run frontend/app.py --server.port 8501

# Or using the runner script
uv run python scripts/run_frontend.py
```

- Streamlit Web Dashboard: `http://localhost:8501`

---

## 5. Running Tests & Quality Checks

### Run Test Suite
```bash
uv run pytest -v
```

### Run Linter & Formatter (Ruff)
```bash
# Check code style and lint rules
uv run ruff check .

# Check code formatting
uv run ruff format --check .

# Auto-fix formatting
uv run ruff format .
```
