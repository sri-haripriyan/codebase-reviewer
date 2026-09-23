# Frontend - Streamlit Application

This directory contains the Streamlit frontend for the AI Codebase Reviewer system.

## Running Locally

To run the Streamlit frontend using `uv`:

```bash
uv run streamlit run frontend/app.py --server.port 8501
```

Or using the convenience script:

```bash
uv run python scripts/run_frontend.py
```

## Features in this Phase

- Backend health monitoring (`GET /health`)
- Responsive sidebar with system metadata
- Architectural workflow overview
