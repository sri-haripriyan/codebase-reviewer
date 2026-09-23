# System Architecture Blueprint

## 1. Overview & Core Mission

The **AI Codebase Reviewer & Report Generator** is an enterprise-grade platform designed to ingest complex codebases, perform in-depth multi-dimensional architectural and security analyses, orchestrate autonomous specialized agents using **LangGraph**, pause for human review and steering, and export executive-ready reports in PDF and DOCX formats.

```
┌────────────────────────────────────────────────────────┐
│                   Streamlit Frontend                   │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / REST
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
├────────────────────────────────────────────────────────┤
│  API Routers (v1)                                      │
│  ├── /health                                           │
│  ├── /repositories   (Ingestion & Processing)          │
│  ├── /analysis       (LangGraph Agent Orchestration)   │
│  ├── /chat           (Project-aware Conversational Q&A)│
│  └── /reports        (Structured PDF/DOCX Export)      │
├────────────────────────────────────────────────────────┤
│  Service & Business Logic Layers                       │
│  ├── Ingestion Service (Git cloner, ZIP extractor)     │
│  ├── Parser & Chunking Engine (Tree-sitter / AST)      │
│  ├── Retrieval & Embedding Service (pgvector)          │
│  ├── LangGraph Multi-Agent Workflow                    │
│  │   ├── Architecture Agent                            │
│  │   ├── Code Quality & Security Agent                 │
│  │   ├── Dependency & Tech Stack Agent                 │
│  │   └── Report Synthesizer Agent                      │
│  │   └── [Human-in-the-Loop Pause & Approval Node]     │
│  └── Document Generation Service (WeasyPrint / docx)   │
└───────────────────────────┬────────────────────────────┘
                            │ SQLAlchemy Async
┌───────────────────────────▼────────────────────────────┐
│         Local PostgreSQL Database + pgvector           │
│  ├── repositories (metadata, branch, commit)           │
│  ├── files (relative path, language, size)             │
│  ├── code_chunks (file_id, chunk_index, content)       │
│  ├── embeddings (chunk_id, vector(1536), model)        │
│  ├── analysis_runs (run_id, graph_state, status)       │
│  └── reports (run_id, structured_json, approval_status)│
└────────────────────────────────────────────────────────┘
```

---

## 2. End-to-End Analysis Lifecycle (11 Stages)

1. **Repository Ingestion**: User provides a GitHub repository URL or uploads a project ZIP file.
2. **Parsing & Chunking**: The project files are parsed into semantic units (modules, classes, functions) using syntax-aware chunking.
3. **Vector & Relational Storage**: Chunks, metadata, and dense embeddings are persisted in local PostgreSQL using the `pgvector` extension.
4. **Project-Aware Conversational Q&A**: Hybrid search (dense vector similarity + lexical BM25/trigram) powers an interactive Q&A assistant.
5. **LangGraph Agent Orchestration**: A directed state graph coordinates specialized agents:
   - *Architecture Agent*: Identifies module boundaries, design patterns, and anti-patterns.
   - *Quality & Security Agent*: Audits vulnerabilities, code smells, and error handling.
   - *Dependency Agent*: Evaluates license compliance, outdated packages, and tech stack choices.
6. **Structured Synthesis**: The agents synthesize findings into a unified hierarchical JSON report schema.
7. **Human-in-the-Loop Interruption**: The LangGraph state pauses at an approval node using checkpointers.
8. **User Review & Feedback Loop**: The user reviews the draft report in the Streamlit frontend and can either approve it or submit corrective guidance to trigger targeted regeneration.
9. **Final Report Export**: The approved report is converted into styled PDF and DOCX documents with executive summaries, metrics, and diagrams.
10. **FastAPI Services**: All workflows are exposed asynchronously via REST endpoints with task status polling or Server-Sent Events.
11. **Streamlit UI**: An intuitive web interface exposes repository management, live analysis tracing, human review forms, and downloads.

---

## 3. Database Schema Design (PostgreSQL + pgvector)

- **`repositories`**: Primary record of analyzed projects (`id`, `name`, `source_type`, `source_url`, `created_at`).
- **`files`**: Inventory of source files (`id`, `repo_id`, `path`, `extension`, `line_count`, `checksum`).
- **`code_chunks`**: Individual segmented pieces of code (`id`, `file_id`, `chunk_index`, `symbol_name`, `content`, `token_count`).
- **`chunk_embeddings`**: High-dimensional vectors (`id`, `chunk_id`, `embedding vector(1536)`, `model_name`).
- **`analysis_sessions`**: LangGraph execution state, checkpoint IDs, and review flags (`id`, `repo_id`, `state`, `status`).
- **`reports`**: Draft and approved reports (`id`, `session_id`, `content_json`, `status`, `approved_at`).

---

## 4. LangGraph Multi-Agent Orchestration & Human Review

```
[Start] ──> [Ingestion Check]
                 │
                 ▼
        [Parallel Agent Execution]
        ├── Architecture Agent
        ├── Security & Quality Agent
        └── Dependencies Agent
                 │
                 ▼
        [Synthesis Agent]
                 │
                 ▼
     [Human Review Gate (Pause)] <──────┐
                 │                      │ Feedback
                 ├─── Request Changes ──┘
                 │
                 └─── Approve
                         │
                         ▼
             [Document Generation] ──> [End]
```

The LangGraph workflow utilizes persistent PostgreSQL checkpointers to pause execution, allowing human feedback to be injected before generating the final deliverable.
