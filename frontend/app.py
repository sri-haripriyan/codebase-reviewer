"""Streamlit frontend dashboard for AI Codebase Reviewer."""

import os
from datetime import datetime

import httpx
import streamlit as st

st.set_page_config(
    page_title="AI Codebase Reviewer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")


def check_backend_health() -> dict | None:
    """Query backend health check endpoint."""
    try:
        response = httpx.get(f"{BACKEND_API_URL}/health", timeout=3.0)
        if response.status_code == 200:
            return response.json()
    except Exception:
        return None
    return None


# Sidebar
with st.sidebar:
    st.title("⚙️ System Status")
    health_data = check_backend_health()

    if health_data:
        st.success("● Backend Online")
        st.markdown(f"**App:** `{health_data.get('app_name', 'N/A')}`")
        st.markdown(f"**Version:** `{health_data.get('version', 'N/A')}`")
        st.markdown(f"**Env:** `{health_data.get('environment', 'N/A')}`")
        st.caption(f"Backend URL: {BACKEND_API_URL}")
    else:
        st.error("○ Backend Offline")
        st.caption(f"Cannot reach {BACKEND_API_URL}/health")
        if st.button("🔄 Retry Connection"):
            st.rerun()

    st.divider()
    st.markdown("### 📋 Navigation")
    st.info(
        "Repository initialization phase active. "
        "Analysis modules will be enabled in upcoming phases."
    )


# Main Content Area
st.title("🔍 AI Codebase Reviewer & Report Generator")
st.markdown(
    """
    **Production-oriented AI codebase analysis and structured report generation system.**

    This platform will ingest codebases (GitHub URL or ZIP), store semantic code chunks
    and embeddings in **PostgreSQL + pgvector**, coordinate specialized analysis agents with
    **LangGraph**, provide human-in-the-loop review workflows, and generate comprehensive
    architectural reports in PDF/DOCX formats.
    """
)

st.divider()

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("1. Ingestion & Storage")
    st.markdown(
        """
        - GitHub repo cloning & ZIP upload
        - AST & semantic code parsing
        - PostgreSQL + pgvector chunk storage
        """
    )
with col2:
    st.subheader("2. Multi-Agent Analysis")
    st.markdown(
        """
        - LangGraph orchestration
        - Specialized analysis agents
        - Project-aware conversational Q&A
        """
    )
with col3:
    st.subheader("3. Review & Reporting")
    st.markdown(
        """
        - Human-in-the-loop review pause
        - Report approval & regeneration
        - Exportable PDF and DOCX reports
        """
    )

st.divider()

st.subheader("🚀 Local System Verification")
if health_data:
    st.json(health_data)
else:
    st.warning(
        f"Backend is not currently responding at `{BACKEND_API_URL}`. "
        "Start the backend using `uv run python scripts/run_backend.py` "
        "or `uv run uvicorn backend.app.main:app --reload`."
    )

formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"AI Codebase Reviewer | Local Environment | Timestamp: {formatted_time}")
