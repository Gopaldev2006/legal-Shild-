# Secure AI Assistant for Legal Data Analysis

> **B.Tech Major Project** • Security-Aware Legal RAG & Intelligence Platform

## Project Overview

**Secure AI Assistant for Legal Data Analysis** is a security-focused AI platform designed to deliver legal data analysis and assistance across two strict user access tiers:

1. **Public User Tier**:
   - General legal information Q&A with mandatory disclaimers.
   - Zero access to confidential case files or professional RAG stores.
2. **Verified Legal Professional Tier**:
   - Secure document upload, open-source OCR, and chunking.
   - Permission-aware RAG over authorized legal documents using local FAISS vector search.
   - Small Language Model (SLM) reasoning for legal arguments, case similarity retrieval, and verdict extraction.
   - Tamper-evident audit logging and 5-layer prompt-injection defense.

---

## 📁 Monorepo Directory Structure

```text
secure-legal-ai/
├── backend/                  # FastAPI Python backend application
│   ├── app/                  # Core application source code
│   │   ├── api/              # REST API endpoints (auth, rag, docs, admin, cases)
│   │   ├── core/             # Configuration & environment loader
│   │   ├── models/           # SQLAlchemy database models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # RAG, Security, Vector, SLM, Document services
│   │   └── main.py           # FastAPI entry point
│   ├── requirements.txt      # Python dependencies
│   └── pytest.ini            # Pytest configuration
├── frontend/                 # React 18 + Vite + Tailwind CSS dashboard
│   ├── src/                  # React components & pages
│   │   ├── components/       # Reusable UI widgets (RAGChatbot, Toast, Modals)
│   │   ├── pages/            # Page views (LandingPage, Login, Register, Dashboards)
│   │   ├── context/          # AuthContext JWT authentication provider
│   │   └── App.jsx           # Main navigation & routing layout
│   └── package.json          # Node dependencies & build scripts
├── data/                     # Local vector stores & processed chunk datasets
├── models/                   # Local SLM weights & embedding model storage
├── tests/                    # Pytest test suite (95 automated tests)
├── docs/                     # Comprehensive Architecture, API, Security, Setup, Testing & Evaluation reports
│   ├── architecture.md       # Complete System Architecture & Sequence Flow
│   ├── api.md                # Full REST API Specification
│   ├── security.md           # 5-Layer Prompt Injection & RBAC Specification
│   ├── setup.md              # Detailed Step-by-Step Setup Guide
│   ├── testing-report.md     # 95 Automated Pytest Execution Report & Matrix
│   └── evaluation.md         # Empirical Latency Breakdown & Metrics
└── README.md                 # Project Overview & Quick Start
```

---

## ⚙️ Step-by-Step Setup Instructions

### 1. Backend Setup (FastAPI)
```bash
cd secure-legal-ai/backend
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
- API Docs (Swagger UI): `http://127.0.0.1:8000/docs`
- Health Endpoint: `http://127.0.0.1:8000/api/v1/health`

### 2. Frontend Setup (React + Vite + Tailwind CSS)
```bash
cd secure-legal-ai/frontend
npm install
cp .env.example .env
npm run dev
```
- Application Web Dashboard: `http://localhost:5173`

### 3. Automated Test Suite Execution
```bash
cd secure-legal-ai
python -m pytest
```

---

## 📋 Final System Status Report

| Major Module | Description | Final Status |
| :--- | :--- | :---: |
| **Authentication & RBAC** | Registration, Login, JWT tokens, Passlib/Bcrypt password hashing, Role enforcement (`PUBLIC_USER`, `UNVERIFIED`, `VERIFIED`, `ADMIN`). | **COMPLETE** |
| **Two-Tier Access Scope** | Public educational general Q&A vs Verified Professional RAG isolation. | **COMPLETE** |
| **Professional Verification Queue** | Bar Council credential submission, OCR text extraction, Admin review modal. | **COMPLETE** |
| **Document Ingestion & OCR** | PDF/DOCX/TXT file uploader, open-source text extraction, cleaning, sliding-window chunking, SHA-256 hashing. | **COMPLETE** |
| **Vector Search Engine (FAISS)** | SentenceTransformers embeddings, FAISS indexing, owner-scoped (`owner_id == user_id`) pre-generation filtering. | **COMPLETE** |
| **Case Precedents & Clustering** | Semantic similarity search across public academic legal judgments; K-Means case clustering engine. | **COMPLETE** |
| **Arguments & Verdict Extraction** | Extraction of cited statutes, key contentions, and holding summary. | **COMPLETE** |
| **5-Layer Prompt Injection Defense** | Direct jailbreak detection, indirect document injection scanning, untrusted data XML encapsulation, system prompt leak protection. | **COMPLETE** |
| **Privacy & PII Protection** | Cross-user/cross-matter access refusal, PII detection & masking (SSN, Aadhar, Credit Cards). | **COMPLETE** |
| **Decoupled Citation Validator** | Decoupled 5-tier citation validator (document existence, chunk existence, owner check, text match). | **COMPLETE** |
| **Small Language Model (SLM) Engine**| Local SLM (TinyLlama-1.1B) PyTorch integration, low-temperature hallucination prevention, Mock fallback mode. | **COMPLETE** |
| **Tamper-Evident Audit Trail** | Timestamped SQLite audit logger for RAG query sessions & security threat alerts. | **COMPLETE** |
| **Admin Control Center** | 6 metric KPI cards, user management, verification review queue, document audit, security threat logs, model status. | **COMPLETE** |
| **Modern Legal AI Dashboard UI** | Clean, minimal, trustworthy light theme UI with 17 supported pages/views, responsive layout, toast notifications. | **COMPLETE** |
| **Documentation & Evaluation** | Complete system documentation (`architecture.md`, `api.md`, `security.md`, `setup.md`, `testing-report.md`, `evaluation.md`). | **COMPLETE** |
