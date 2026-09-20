# LexGuard AI — Project Brain

> Quick reference for developers and AI agents working on this codebase.

---

## What Is This?

**LexGuard AI** is a B.Tech Major Project — a security-focused AI platform for legal data analysis.

- **Two-tier access:** Public (general legal Q&A) and Verified Legal Professional (full RAG + document analysis)
- **Stack:** FastAPI (Python) + React 18 + Vite + TailwindCSS + SQLite + SentenceTransformers + Google Gemini

---

## Quick Start

```bash
# Backend
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1      # Windows
cp .env.example .env             # fill in your values
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

- **Frontend:** http://localhost:5173
- **Backend API:** http://127.0.0.1:8000
- **Swagger docs:** http://127.0.0.1:8000/docs

---

## Demo Accounts (seeded on first run)

| Role | Email | Password |
|---|---|---|
| Public User | `public@example.com` | `public123` |
| Unverified Pro | `unverified@example.com` | `unverified123` |
| Verified Pro | `advocate@example.com` | `advocate123` |
| Admin | `admin@example.com` | `admin123` |

---

## Project Structure

```
secure-legal-ai/
├── backend/                   # FastAPI Python backend
│   ├── app/
│   │   ├── api/               # Route handlers (auth, documents, rag, chat, admin, ...)
│   │   ├── core/              # Config, security, permissions, limiter
│   │   ├── db/                # SQLAlchemy session, base, init_db
│   │   ├── models/            # ORM models (User, Document, Conversation, AuditLog, ...)
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business logic (RAG, analysis, audit, AI, retrieval, ...)
│   │   └── main.py            # FastAPI app entry point
│   ├── tests/                 # 197 automated security tests
│   ├── requirements.txt
│   └── .env.example
├── frontend/                  # React 18 + Vite + TailwindCSS
│   ├── src/
│   │   ├── components/        # Reusable UI components
│   │   ├── context/           # AuthContext (JWT management)
│   │   ├── pages/             # LandingPage, Login, Register, Dashboards
│   │   └── services/          # chatApi.js, API wrappers
│   └── package.json
├── docs/                      # Architecture, API, security, setup, testing docs
├── data/                      # Local data (gitignored except README)
├── models/                    # SLM model weights (gitignored)
├── training/                  # SLM fine-tuning scripts
├── tests/                     # Root-level integration tests
├── brain.md                   # This file
├── README.md                  # Project overview
└── .env.example               # Environment variable template
```

---

## Key Environment Variables

See `backend/.env.example` for full list. Critical ones:

| Variable | Purpose |
|---|---|
| `JWT_SECRET_KEY` | HMAC-SHA256 signing key — generate with `secrets.token_hex(48)` |
| `GEMINI_ENCRYPTION_KEY` | Fernet key for encrypting user Gemini API keys at rest |
| `GEMINI_API_KEY` | System-level Google Gemini API key (optional — free engine fallback) |
| `DATABASE_URL` | SQLite path (dev) or PostgreSQL URL (prod) |
| `REVOCATION_ENABLED` | `true` = check jti on every request (session revocation) |
| `RATE_LIMIT_*` | Per-endpoint rate limits (e.g. `RATE_LIMIT_LOGIN=5/minute`) |

**Never commit real values. Use `.env.example` for placeholders.**

---

## Security Architecture

```
Request → CORS → Rate Limiter → JWT decode + jti check
       → Role check (require_professional / require_admin)
       → Ownership check (owner_id == user_id)
       → File validation (magic bytes + extension + size)
       → Business logic (owner-scoped SQL)
       → Audit log write (append-only, secrets stripped)
```

**Key security features:**
- `slowapi` rate limiting (5/min login, 10/min RAG, etc.)
- File validation: extension whitelist + magic bytes + DOCX ZIP structure
- JWT with `jti` — server-side revocation via `user_sessions` table
- Fernet-encrypted Gemini API key storage
- Append-only `audit_logs` table — 18 event types
- `_sanitise_metadata()` strips password/token/api_key from audit records

---

## API Routers

| Prefix | File | Notes |
|---|---|---|
| `/auth` | `api/auth.py` | Register, login, logout, sessions, Gemini key |
| `/documents` | `api/documents.py` | Upload, list, analyze, delete |
| `/rag` | `api/rag.py` | Public query (Tier 1), RAG query (Tier 2), search |
| `/chat` | `api/chat.py` | Persistent conversations (general/document/rag modes) |
| `/admin` | `api/admin.py` | User management, verifications, audit logs, model status |
| `/cases` | `api/cases.py` | Academic case search + clustering |
| `/vector` | `api/vector.py` | Vector store operations |
| `/system` | `api/system.py` | Benchmarks + compliance report |
| `/verification` | `api/verification.py` | Bar credential submission |

---

## Database Models

| Model | Table | Key Fields |
|---|---|---|
| `User` | `users` | `role`, `verification_status`, `encrypted_gemini_api_key` |
| `LegalDocument` | `legal_documents` | `owner_id`, `stored_path` (UUID), `processing_status` |
| `DocumentChunk` | `document_chunks` | `owner_id` (denormalised), `embedding`, `is_embedded` |
| `Conversation` | `conversations` | `owner_id`, `mode` (general/document/rag), `document_id` |
| `ChatMessage` | `chat_messages` | `role`, `content`, `sources_json`, `model_used` |
| `UserSession` | `user_sessions` | `jti`, `revoked_at`, `expires_at` |
| `AuditLog` | `audit_logs` | `event_type`, `user_id`, `resource_type`, `success`, `metadata_json` |
| `RAGAuditLog` | `rag_audit_logs` | `query_text`, `provider_used`, `chunks_retrieved` |

---

## Test Suite

```bash
cd backend
python -m pytest tests/ -v
# 197 passed, 1 skipped, 0 failed
```

| File | Tests | What it covers |
|---|---|---|
| `test_phase7_security.py` | 47 | Final security audit — all acceptance criteria |
| `test_rbac.py` | 64 | Role × endpoint matrix + ownership |
| `test_session_management.py` | 19 | JWT jti, revocation, session lifecycle |
| `test_rate_limiting.py` | 28 | Rate limits, 429 responses, headers |
| `test_file_validation.py` | 25 | Magic bytes, path traversal, oversized, fake files |
| `test_chat_security.py` | 15 | Chat ownership, idempotency, context isolation |

---

## Document Analysis Phases

1. Upload + Chunking + Embeddings
2. Summary
3. Clauses + Obligations
4. Risk Assessment
5. Missing + Ambiguous Clauses
6. Entities (Parties, Dates, Obligations with evidence)

---

## Notes for AI Agents

- **Never** modify `backend/.env` — it contains real credentials
- **Never** log message content, API keys, or tokens
- `write_audit_event()` never raises — failures are swallowed
- `create_access_token()` returns `(token_str, jti)` — both are needed
- `require_professional` in `permissions.py` is the single RBAC source of truth
- `_sanitise_metadata()` in `audit_service.py` strips secrets from all audit records
- All document DB queries must filter by `owner_id` — never by `document_id` alone
