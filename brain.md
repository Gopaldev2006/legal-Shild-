# LexGuard AI — Project Brain

> **Living document. Updated with every code change.**
> Source code always wins over this file if they conflict.

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Name** | LexGuard AI |
| **Full title** | Secure AI Assistant for Legal Data Analysis |
| **Type** | B.Tech Major Project — Full-stack AI web application |
| **Target users** | Public users (general legal Q&A) and Verified Legal Professionals (document RAG + analysis) |
| **Problem solved** | Secure, role-gated AI-powered legal document analysis and Q&A with full audit trail |
| **Status** | ✅ Complete — all features implemented and verified. 239 automated tests passing (0 failures). |

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React 18 + Vite + TailwindCSS | SPA dashboard (no routing library) |
| Backend | FastAPI (Python) + Uvicorn | REST API server |
| Database | SQLAlchemy + SQLite (`data/secure_legal.db`) | ORM + relational storage |
| Authentication | JWT (PyJWT) + bcrypt (passlib) | Token-based auth with session revocation |
| Session revocation | Custom `UserSession` table + JTI | Server-side logout and revoke-all |
| Authorization | Custom RBAC (`permissions.py`) + `deps.py` | 3-tier role system |
| AI — Primary | Google Gemini API (`gemini-2.0-flash`) | Legal reasoning and document analysis |
| AI — Fallback | Built-in Free AI Legal Engine | Works without any API key |
| AI — Local SLM | TinyLlama-1.1B-Chat-v1.0 (optional) | On-device inference |
| RAG | FAISS + `sentence-transformers` (all-MiniLM-L6-v2, 384-dim) | Semantic chunk retrieval |
| Embeddings | `sentence-transformers` | Float32 vectors stored as base64 in SQLite |
| PDF extraction | `pypdf` | Page-by-page text extraction |
| DOCX extraction | `python-docx` | Paragraph text extraction (no macros) |
| Rate limiting | SlowAPI (`slowapi==0.1.9`) | Per-endpoint IP-based throttling |
| Encryption | `cryptography` (Fernet + PBKDF2) | Gemini API key at-rest encryption |
| Styling | TailwindCSS 3 + lucide-react | Utility CSS + icons |
| Testing | pytest + httpx | 197 automated tests |

---

## 3. Project Architecture

```
Browser (React SPA)
        │
        │  HTTP/JSON
        ▼
FastAPI Backend  (uvicorn, port 8000)
        │
        ├── CORS Middleware          (explicit origin whitelist)
        ├── SlowAPI Rate Limiter     (per-endpoint, IP-based)
        │
        ├── JWT decode + jti check   (get_current_user)
        ├── Role check               (require_professional / require_admin)
        ├── Ownership check          (owner_id == user_id)
        │
        ├── File Validator           (magic bytes, extension, size)
        │
        ├── Business Logic
        │     ├── RAG pipeline       (embed → retrieve → Gemini/fallback → answer)
        │     ├── Document analysis  (6-phase: summary, clauses, risk, entities…)
        │     ├── Persistent chat    (Conversation + ChatMessage + sources)
        │     └── Admin controls     (users, verifications, audit logs)
        │
        ├── Audit log write          (append-only, secrets stripped)
        │
        └── SQLite Database
              (users, sessions, documents, chunks, conversations,
               messages, audit_logs, rag_audit_logs, legal_cases)
```

---

## 4. Directory Structure

```
secure-legal-ai/
│
├── brain.md                     ← THIS FILE — living project knowledge
├── README.md                    ← Project overview + quick start
├── .gitignore
├── .env.example                 ← Root placeholder (see backend/.env.example)
├── pytest.ini
│
├── backend/
│   ├── .env.example             ← All env var names + descriptions (NO real values)
│   ├── requirements.txt         ← Python dependencies (20 packages)
│   ├── pytest.ini
│   │
│   ├── app/
│   │   ├── main.py              ← FastAPI entry point; startup, middleware, routes
│   │   │
│   │   ├── core/
│   │   │   ├── config.py        ← All settings (pydantic-settings, loads .env)
│   │   │   ├── security.py      ← bcrypt, Fernet encryption, JWT create/decode
│   │   │   ├── permissions.py   ← RBAC: require_professional, require_admin, ownership helpers
│   │   │   └── limiter.py       ← Shared SlowAPI limiter instance
│   │   │
│   │   ├── api/
│   │   │   ├── router.py        ← Registers all 10 sub-routers under /api/v1
│   │   │   ├── deps.py          ← get_current_user (4-step chain), require_roles
│   │   │   ├── auth.py          ← Login, register, logout, sessions, Gemini key mgmt
│   │   │   ├── documents.py     ← Upload, list, get, analyze, delete
│   │   │   ├── rag.py           ← public-query (T1), /query (T2), /search, audit-history
│   │   │   ├── chat.py          ← Conversations + messages (general/document/rag modes)
│   │   │   ├── admin.py         ← Dashboard, users, verifications, audit-logs, model-status
│   │   │   ├── cases.py         ← Academic case search + K-Means clustering
│   │   │   ├── vector.py        ← Vector store operations (search, index, reindex-all)
│   │   │   ├── verification.py  ← Bar credential submission (file upload + OCR)
│   │   │   ├── system.py        ← Benchmarks + compliance report
│   │   │   └── health.py        ← Health check endpoint
│   │   │
│   │   ├── models/
│   │   │   ├── user.py          ← User, UserRole, VerificationStatus
│   │   │   ├── document.py      ← LegalDocument, DocumentChunk
│   │   │   ├── conversation.py  ← Conversation, ChatMessage
│   │   │   ├── session.py       ← UserSession (JTI revocation)
│   │   │   ├── audit_log.py     ← AuditLog, AuditEventType (25 events)
│   │   │   ├── audit.py         ← RAGAuditLog (legacy compliance table)
│   │   │   ├── case.py          ← LegalCase (public academic dataset)
│   │   │   └── verification.py  ← VerificationRequest
│   │   │
│   │   ├── schemas/             ← Pydantic request/response schemas
│   │   │   ├── user.py          ← UserRegister, UserLogin, TokenResponse, SessionResponse
│   │   │   ├── document.py      ← DocumentResponse, DocumentAnalysisResponse (rich)
│   │   │   ├── conversation.py  ← ConversationCreate, SendMessageRequest/Response
│   │   │   ├── rag.py           ← RAGAnswerRequest/Response, SemanticSearchRequest
│   │   │   └── …
│   │   │
│   │   ├── services/
│   │   │   ├── ai/
│   │   │   │   ├── gemini_service.py      ← Gemini API client (3 SDK fallbacks + REST)
│   │   │   │   └── free_ai_service.py     ← Built-in legal Q&A fallback
│   │   │   ├── audit/
│   │   │   │   └── audit_service.py       ← write_audit_event() — never raises
│   │   │   ├── document/
│   │   │   │   ├── extractor.py           ← PDF/DOCX text extraction
│   │   │   │   ├── chunker.py             ← Sliding-window chunking (1000 chars, 150 overlap)
│   │   │   │   ├── cleaner.py             ← Text normalization
│   │   │   │   ├── file_validator.py      ← Magic bytes + extension + size + structure
│   │   │   │   ├── document_analysis_service.py  ← 8-section analysis orchestrator
│   │   │   │   ├── summary_service.py     ← Phase 2: document summary
│   │   │   │   ├── clause_analysis_service.py    ← Phase 3: clauses + obligations
│   │   │   │   ├── risk_analysis_service.py      ← Phase 4: risk identification
│   │   │   │   ├── missing_ambiguous_service.py  ← Phase 5: missing/ambiguous clauses
│   │   │   │   └── entities_extraction_service.py ← Phase 6: parties, dates, obligations
│   │   │   ├── embedding/
│   │   │   │   └── embedding_service.py   ← all-MiniLM-L6-v2, 384-dim, singleton
│   │   │   ├── rag/
│   │   │   │   ├── rag_service.py         ← Tier 1 public query + argument extraction
│   │   │   │   ├── rag_answer_service.py  ← Tier 2 grounded RAG (6-step pipeline)
│   │   │   │   ├── context_builder.py     ← Formats retrieved chunks into prompt context
│   │   │   │   └── prompt_builder.py      ← Constructs XML-isolated prompt
│   │   │   ├── retrieval/
│   │   │   │   └── retrieval_service.py   ← retrieve_relevant_chunks() with owner_id filter
│   │   │   ├── vector/
│   │   │   │   ├── vector_repository.py   ← FAISS index management
│   │   │   │   └── retrieval_service.py   ← UserContext-based search
│   │   │   ├── cases/                     ← Academic case search + clustering
│   │   │   ├── security/
│   │   │   │   ├── prompt_injection/      ← 5-layer injection detection
│   │   │   │   └── privacy/               ← PII detection, access validation
│   │   │   └── system/                    ← Benchmarks, compliance report
│   │   │
│   │   └── db/
│   │       ├── base.py          ← SQLAlchemy Base
│   │       ├── session.py       ← Engine + SessionLocal (SQLite check_same_thread=False)
│   │       └── init_db.py       ← Seeds 4 demo accounts on startup
│   │
│   └── tests/                   ← 16 test files, 197 tests pass
│
├── frontend/
│   ├── package.json             ← React 18, Vite 5, TailwindCSS 3, lucide-react
│   ├── vite.config.js           ← Vite config (proxy to backend :8000)
│   ├── tailwind.config.js
│   └── src/
│       ├── main.jsx             ← React entry point
│       ├── App.jsx              ← Root: AuthProvider wrapper, view state machine
│       ├── context/
│       │   └── AuthContext.jsx  ← JWT storage (localStorage), login/logout/register
│       ├── pages/
│       │   ├── LandingPage.jsx
│       │   ├── LoginPage.jsx
│       │   ├── RegisterPage.jsx
│       │   ├── PublicDashboard.jsx   ← Tier 1: public Q&A + verification apply
│       │   ├── ProfessionalDashboard.jsx ← Tier 2: documents, RAG, analysis, chat
│       │   └── AdminDashboard.jsx    ← Admin: users, verifications, audit logs
│       ├── components/
│       │   ├── RAGChatbot.jsx        ← Stateless direct RAG query (non-persistent)
│       │   ├── PersistentChat.jsx    ← Full chat history dashboard (Phase 5)
│       │   ├── DocumentAnalysisPanel.jsx ← 8-section analysis results
│       │   ├── DocumentUploadModal.jsx
│       │   ├── DocumentDetailsModal.jsx
│       │   ├── CaseDetailsModal.jsx
│       │   ├── VerificationRequestModal.jsx
│       │   ├── HealthStatus.jsx
│       │   ├── LegalDisclaimer.jsx
│       │   ├── PaginationControls.jsx
│       │   └── Toast.jsx
│       └── services/
│           └── chatApi.js       ← All /chat/* API wrappers with error mapping
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── api.md
│   ├── security.md
│   ├── setup.md
│   ├── evaluation.md
│   └── testing-report.md        ← 197 tests, full security audit
│
├── tests/                       ← Root integration tests (17 files)
├── training/                    ← SLM fine-tuning scripts + datasets
├── scripts/                     ← Helper scripts (run_backend.py, benchmark_slm.py)
├── data/                        ← Runtime data (gitignored except README)
└── models/                      ← SLM weights (gitignored)
```

---

## 5. Backend Architecture — Request Flow

```
HTTP Request
    │
    ├── CORS Middleware              origins from ALLOWED_ORIGINS env var
    │
    ├── SlowAPI Rate Limiter         @limiter.limit(lambda: settings.RATE_LIMIT_*)
    │   └── 429 + Retry-After on breach
    │
    ├── HTTPBearer → JWT decode      PyJWT signature + expiry check
    │   ├── Extract user_id from 'sub'
    │   ├── [REVOCATION_ENABLED] Query user_sessions WHERE jti=? AND revoked_at IS NULL
    │   │   └── 401 if session missing or revoked
    │   ├── UPDATE last_used_at (best-effort)
    │   └── Load User from DB → 401 if not found
    │
    ├── Role check                   require_professional / require_admin
    │   └── 403 if insufficient role
    │
    ├── Ownership check              _assert_owner() / _get_conversation_or_404()
    │   └── 404 (not 403) if wrong owner — prevents existence leakage
    │
    ├── [Uploads only] FileValidator
    │   ├── Filename sanitisation    path traversal, null bytes, absolute paths
    │   ├── Extension whitelist      .pdf, .docx only for documents
    │   ├── Size limit               MAX_DOCUMENT_SIZE_MB (default 10 MB)
    │   ├── Magic bytes              %PDF or PK\x03\x04 must match
    │   └── Structural check         PDF: %%EOF; DOCX: word/document.xml in ZIP
    │
    ├── Business Logic
    │   └── All DB queries scoped by owner_id
    │
    ├── write_audit_event()          best-effort, never raises, secrets stripped
    │
    └── Response
```

---

## 6. Frontend Architecture

**Entry point:** `src/main.jsx` → `<AuthProvider>` → `<AppContent>`

**Navigation:** `App.jsx` manages `currentView` state — no react-router. Views: `landing`, `login`, `register`, `dashboard`.

**Auth state:** `AuthContext.jsx`
- JWT stored in `localStorage` key `sec_legal_token`
- On mount: `GET /api/v1/auth/me` to verify token validity
- `login()` → POST /auth/login → stores token + user
- `logout()` → POST /auth/logout (server revocation) → clears localStorage
- `register()` → POST /auth/register → auto-login

**Dashboard routing by role:**
- `PUBLIC_USER` → `PublicDashboard`
- `LEGAL_PROFESSIONAL` → `ProfessionalDashboard`
- `ADMIN` → `AdminDashboard`

**ProfessionalDashboard tabs:**
- Legal Chat (RAGChatbot — stateless)
- Persistent Chat (PersistentChat — full history)
- Analysis (DocumentAnalysisPanel)
- Documents (table + [Chat] + [Inspect] + [Delete])
- Similar Cases, Clusters, AI Analysis, Audit, Settings (active sessions panel)

**API communication:** Direct `fetch()` calls (no axios). `chatApi.js` provides typed wrappers for all `/chat/*` endpoints with HTTP status → readable error mapping.

---

## 7. Authentication

| Aspect | Implementation |
|---|---|
| Registration | POST /auth/register — role always forced to PUBLIC_USER |
| Login | POST /auth/login — bcrypt verify → JWT issued → UserSession created |
| Token | JWT HS256, 30-minute expiry, contains: sub (user_id), jti (UUID), iat, exp, email, role |
| Sensitive claim block | password, api_key, secret, token, key, hash, encrypted never encoded into JWT |
| Session revocation | Every request: SELECT user_sessions WHERE jti=? → 401 if revoked_at set |
| Logout | POST /auth/logout → sets revoked_at on UserSession → immediate invalidation |
| Revoke all | POST /auth/sessions/revoke-all → revokes all active sessions |
| Password storage | bcrypt (passlib CryptContext, auto-deprecated-algo support) |
| Public endpoints | POST /auth/login, POST /auth/register, POST /rag/public-query |
| Optional auth | get_current_user_optional — used for public-query with personal Gemini key |

---

## 8. Authorization / RBAC

**Roles:** `PUBLIC_USER` → `LEGAL_PROFESSIONAL` (must be VERIFIED) → `ADMIN`

```
PUBLIC_USER
 └── Tier 1: general legal Q&A only

LEGAL_PROFESSIONAL (VERIFIED)
 └── Tier 2: full document/RAG/analysis/chat pipeline

ADMIN
 └── All Tier 2 + user management + verifications + audit logs
```

**Access Matrix:**

| Feature | Public | Professional (verified) | Admin |
|---|---|---|---|
| Public AI Q&A | ✓ | ✓ | ✓ |
| Own profile / sessions | ✓ | ✓ | ✓ |
| Verification submission | ✓ | ✓ | ✓ |
| General chat mode | ✓ | ✓ | ✓ |
| Document upload | ✗ | ✓ | ✓ |
| Document analysis | ✗ | ✓ | ✓ |
| RAG query / search | ✗ | ✓ | ✓ |
| Vector search | ✗ | ✓ | ✓ |
| Document/RAG chat modes | ✗ | ✓ | ✓ |
| Case search / clustering | ✗ | ✓ | ✓ |
| Admin dashboard | ✗ | ✗ | ✓ |
| Audit log viewer | ✗ | ✗ | ✓ |

**Ownership rule:** All resources check `owner_id == current_user.id`. Wrong-owner returns **404** (not 403) to prevent resource existence leakage. ADMIN bypasses ownership.

---

## 9. Database Architecture

### Tables and Relationships

```
users
 ├── user_sessions          (one user → many sessions; JTI revocation)
 ├── legal_documents        (one user → many documents; owner_id FK)
 │     └── document_chunks  (one document → many chunks; owner_id denormalized)
 ├── conversations          (one user → many conversations; optional document_id FK)
 │     └── chat_messages    (one conversation → many messages)
 ├── verification_requests  (one user → many verification attempts)
 └── audit_logs             (one user → many audit events; nullable for pre-auth)

rag_audit_logs              (standalone, user_id FK)
legal_cases                 (public academic dataset, no user ownership)
```

### Model Summary

| Model | Table | Key Fields |
|---|---|---|
| `User` | `users` | `role`, `verification_status`, `encrypted_gemini_api_key` (Fernet) |
| `UserSession` | `user_sessions` | `jti` (unique), `revoked_at` (NULL=active), `expires_at` |
| `LegalDocument` | `legal_documents` | `owner_id`, `stored_path` (UUID name), `processing_status`, `file_hash` (SHA-256) |
| `DocumentChunk` | `document_chunks` | `owner_id` (denorm), `chunk_id` (UUID), `embedding` (base64 float32), `is_embedded` |
| `Conversation` | `conversations` | `owner_id`, `mode` (general/document/rag), `document_id` (nullable) |
| `ChatMessage` | `chat_messages` | `role`, `content`, `sources_json` (JSON array), `model_used` |
| `AuditLog` | `audit_logs` | `event_type` (25 types), `user_id` (nullable), `success`, `metadata_json` |
| `RAGAuditLog` | `rag_audit_logs` | `query_text`, `provider_used`, `chunks_retrieved`, `is_safe` |
| `VerificationRequest` | `verification_requests` | `document_hash`, `extracted_text` (OCR), `status` |
| `LegalCase` | `legal_cases` | Academic case data (title, court, facts, decision, embedding) |

---

## 10. API Endpoints

| Method | Endpoint | Auth | Role | Purpose |
|---|---|---|---|---|
| GET | `/api/v1/health` | None | Any | Health check |
| POST | `/api/v1/auth/register` | None | — | Create PUBLIC_USER account |
| POST | `/api/v1/auth/login` | None | — | Issue JWT + create UserSession |
| POST | `/api/v1/auth/logout` | JWT | Any | Revoke current session |
| GET | `/api/v1/auth/me` | JWT | Any | Current user profile |
| GET | `/api/v1/auth/sessions` | JWT | Any | List own sessions (safe metadata) |
| DELETE | `/api/v1/auth/sessions/{id}` | JWT | Owner | Revoke one session |
| POST | `/api/v1/auth/sessions/revoke-all` | JWT | Any | Revoke all sessions |
| POST | `/api/v1/auth/gemini-api-key` | JWT | Any | Store encrypted Gemini key |
| GET | `/api/v1/auth/gemini-api-key` | JWT | Any | Status + 8-char masked preview |
| DELETE | `/api/v1/auth/gemini-api-key` | JWT | Any | Remove stored key |
| POST | `/api/v1/verification/request` | JWT | Any | Submit bar credential (file upload) |
| GET | `/api/v1/verification/status` | JWT | Owner | Own verification status |
| POST | `/api/v1/rag/public-query` | Optional | Any | Tier 1 general legal Q&A |
| POST | `/api/v1/rag/query` | JWT | Professional | Tier 2 grounded RAG |
| POST | `/api/v1/rag/search` | JWT | Professional | Semantic chunk search |
| GET | `/api/v1/rag/audit-history` | JWT | Professional | Own RAG query history |
| POST | `/api/v1/rag/extract-arguments/{id}` | JWT | Professional | Statute + argument extraction |
| POST | `/api/v1/documents/upload` | JWT | Professional | Upload + process document |
| GET | `/api/v1/documents/` | JWT | Professional | List own documents |
| GET | `/api/v1/documents/{id}` | JWT | Owner | Document metadata |
| GET | `/api/v1/documents/{id}/chunks` | JWT | Owner | Document chunks |
| GET | `/api/v1/documents/{id}/download` | JWT | Owner | Download original file |
| DELETE | `/api/v1/documents/{id}` | JWT | Owner | Delete document + chunks + file |
| POST | `/api/v1/documents/{id}/analyze` | JWT | Owner | 8-section AI analysis |
| POST | `/api/v1/documents/{id}/reprocess` | JWT | Owner | Re-run processing pipeline |
| POST | `/api/v1/chat/conversations` | JWT | Any* | Create conversation |
| GET | `/api/v1/chat/conversations` | JWT | Any | List own conversations |
| GET | `/api/v1/chat/conversations/{id}` | JWT | Owner | Full conversation + messages |
| PATCH | `/api/v1/chat/conversations/{id}` | JWT | Owner | Rename conversation |
| DELETE | `/api/v1/chat/conversations/{id}` | JWT | Owner | Delete conversation + messages |
| POST | `/api/v1/chat/conversations/{id}/messages` | JWT | Owner | Send message → AI response |
| POST | `/api/v1/vector/search` | JWT | Professional | Permission-aware vector search |
| POST | `/api/v1/vector/index-document/{id}` | JWT | Owner | Index document chunks |
| DELETE | `/api/v1/vector/document/{id}` | JWT | Owner | Delete document vectors |
| POST | `/api/v1/vector/reindex-all` | JWT | Admin | Reindex all documents |
| GET | `/api/v1/admin/dashboard-summary` | JWT | Admin | 6-metric KPI cards |
| GET | `/api/v1/admin/users` | JWT | Admin | Paginated user list |
| GET | `/api/v1/admin/verifications` | JWT | Admin | Verification queue |
| POST | `/api/v1/admin/verifications/{id}/approve` | JWT | Admin | Approve + elevate role |
| POST | `/api/v1/admin/verifications/{id}/reject` | JWT | Admin | Reject application |
| GET | `/api/v1/admin/documents` | JWT | Admin | System-wide document audit |
| GET | `/api/v1/admin/security-events` | JWT | Admin | Prompt injection + privacy events |
| GET | `/api/v1/admin/audit-logs` | JWT | Admin | Paginated audit log (filterable) |
| GET | `/api/v1/admin/model-status` | JWT | Admin | SLM + Gemini config |
| GET | `/api/v1/system/metrics` | JWT | Any | Performance benchmarks |
| GET | `/api/v1/system/compliance-report` | JWT | Any* | Security compliance report |

> *Chat general mode: any authenticated user. Chat document/rag mode: Professional/Admin only.
> *compliance-report: Admin sees all; others see own data only.

---

## 11. AI Architecture

### Gemini Integration

```
get_gemini_api_key()
  1. os.getenv("GEMINI_API_KEY")
  2. settings.GEMINI_API_KEY   (loaded from .env)
  3. Direct read of backend/.env  (dev convenience)
        │
        ▼
GeminiService.generate_response(prompt, system_instruction, temperature)
  Try: google-genai SDK
  Try: google.generativeai SDK
  Try: urllib REST (direct HTTP)
        │
  On any failure → return None   (key never logged)
        │
        ▼
Caller uses Free AI Legal Engine fallback
```

**Error safety:** Raw HTTP error bodies never reach the client. Auth errors (400/401/403) logged at WARNING with code only. All failures return `None`.

**User personal keys:** Stored as Fernet ciphertext in `users.encrypted_gemini_api_key`. Decrypted per-request in `deps.py`. GET endpoint returns only masked preview (`AIzaSyFa***`) — never full key.

### Free AI Legal Engine

- File: `backend/app/services/ai/free_ai_service.py`
- Used when Gemini unavailable/fails or GEMINI_API_KEY not set
- Provides general legal topic responses for Tier 1 queries
- For Tier 2 grounded RAG: `_grounded_fallback()` in `rag_answer_service.py` presents retrieved chunk snippets with source attribution — never hallucincates

---

## 12. Document Processing Pipeline

```
POST /documents/upload
    │
    ├── FileValidator
    │   ├── Filename sanitisation  (path traversal, null bytes, absolute paths)
    │   ├── Extension whitelist    (.pdf, .docx only)
    │   ├── Size check             (≤ MAX_DOCUMENT_SIZE_MB = 10 MB)
    │   ├── Magic bytes            (%PDF or PK\x03\x04)
    │   └── Structural check       (PDF: %%EOF; DOCX: word/document.xml in ZIP)
    │
    ├── SHA-256 hash of content
    ├── UUID-based storage filename  (original name kept as metadata only)
    ├── Save to data/documents/
    │
    └── Processing Pipeline (status: UPLOADING → PROCESSING → CHUNKING → EMBEDDED → READY)
          │
          ├── PROCESSING: extractor.py → PDF: pypdf page-by-page; DOCX: paragraphs only (no macros)
          ├── CHUNKING:   chunker.py → 1000 char chunks, 150 char overlap, sliding window
          ├── EMBEDDING:  EmbeddingService (all-MiniLM-L6-v2, 384-dim)
          │              → float32 ndarray → base64 bytes → stored in document_chunks.embedding
          └── READY:      is_embedded=True for all chunks

On failure: status=FAILED, safe error message stored (no internals exposed)
```

---

## 13. RAG Architecture

```
User Query
    │
    ├── Query Embedding     (same all-MiniLM-L6-v2 model)
    │
    ├── retrieve_relevant_chunks()
    │   ├── SQL: owner_id == user_id AND document_id == X (if document-scoped)
    │   ├── Cosine similarity (dot product of L2-normalized vectors)
    │   ├── Threshold filter: similarity ≥ 0.35
    │   └── Top-K: RAG_TOP_K = 5
    │
    ├── No results? → Return structured "No Relevant Information Found" message
    │
    ├── build_context() → formats chunks as SOURCE 1 / SOURCE 2 ... blocks
    │
    ├── _build_history_block()  → last 20 turns, capped at 8000 chars
    │
    ├── Try Gemini  (if api_key starts with "AIzaSy")
    │   └── system_prompt + history + context + user question → GeminiService
    │
    └── Fallback: _grounded_fallback() → presents raw chunk snippets
          │
          └── RAGAnswerResult(answer, sources, used_rag, provider_used, no_relevant_context)

Sources: [{chunk_id, document_id, filename, page_number, similarity, matter_id, jurisdiction}]
Saved as sources_json on ChatMessage for display in frontend.
```

---

## 14. Document Analysis — 8 Sections

**Endpoint:** `POST /api/v1/documents/{id}/analyze`
**Requires:** Document status READY or COMPLETED, owner or Admin

| Phase | Service | Output |
|---|---|---|
| 1 | `summary_service.py` | executive_summary, document_type, purpose, main_subject, key_takeaways, sources |
| 2 | `clause_analysis_service.py` | 19 clause types with importance (high/medium/low), source references |
| 3 | `risk_analysis_service.py` | overall_risk, risk_score, identified risks with severity + evidence |
| 4 | `missing_ambiguous_service.py` | missing standard clauses, ambiguous language, conflicting provisions |
| 5 | `entities_extraction_service.py` | parties with roles, key dates (15 types), obligations with evidence |
| Legacy | `document_analysis_service.py` | summary, important_clauses, risks (string arrays for backward compat) |

All phases: Gemini primary → rule-based fallback. Text capped at `MAX_ANALYSIS_CHARS=12000`.

---

## 15. Persistent AI Chat

**Conversation modes:**
- `general` — any authenticated user; routes to `rag_service.process_public_query()`
- `document` — Professional/Admin only; RAG scoped to one linked document
- `rag` — Professional/Admin only; RAG across all user documents

```
POST /chat/conversations/{id}/messages
    │
    ├── Idempotency guard         (same content + role within 10s → return cached pair)
    ├── Save user ChatMessage     (db.flush — no commit yet)
    ├── Auto-generate title       (from first message, legal keyword extraction, deterministic)
    │
    ├── _dispatch_ai()
    │   ├── GENERAL mode → process_public_query()
    │   ├── DOCUMENT mode → rag_answer(document_id=conv.document_id, history=last_20_msgs)
    │   └── RAG mode → rag_answer(document_id=None, history=last_20_msgs)
    │
    ├── On AI failure → HTTP 500 + db.rollback()  (no fake messages saved)
    │
    ├── Save assistant ChatMessage + sources_json
    ├── Update conversation.updated_at
    └── Return {user_message, assistant_message, conversation}
```

**Frontend history dashboard (Phase 5):**
- Grouped by Today / Yesterday / Earlier
- Per-session `last_used_at` tracking
- 3-step typing indicator (Searching → Retrieving → Generating)
- Source cards with filename, page, match %
- Responsive height: `calc(100vh - 260px)`

---

## 16. Security Architecture

### Rate Limiting (slowapi 0.1.9, in-memory)

| Endpoint | Limit | Purpose |
|---|---|---|
| POST /auth/login | 5/minute | Brute-force protection |
| POST /auth/register | 10/minute | Account spam |
| POST /rag/public-query | 20/minute | AI cost protection |
| POST /rag/query | 10/minute | RAG compute |
| POST /documents/upload | 5/minute | Pipeline abuse |
| POST /documents/{id}/analyze | 5/minute | AI cost |
| POST /chat/conversations/{id}/messages | 20/minute | Chat flooding |
| POST /chat/conversations | 20/minute | Conversation spam |

Response: HTTP 429 + `Retry-After` header + `{"error": "Too many requests. Please try again later."}`

**Production note:** Switch to Redis storage for multi-worker deployments.

### File Validation

1. Filename: path traversal (`..`), absolute paths (`/`, `C:\`), null bytes, forbidden chars
2. Extension: `.pdf` and `.docx` only (verification also accepts image types)
3. Size: ≤ `MAX_DOCUMENT_SIZE_MB` (10 MB default)
4. Magic bytes: `%PDF` for .pdf; `PK\x03\x04` for .docx
5. Structure: PDF must have `%%EOF`; DOCX must be valid ZIP containing `word/document.xml`
6. Storage: UUID-based filename; original name stored as metadata only

### JWT + Sessions

- Token: 30-minute expiry, HS256, contains `jti` UUID
- Revocation: every request queries `user_sessions` by `jti`; `revoked_at` set on logout
- `POST /auth/sessions/revoke-all` invalidates all devices simultaneously
- Pre-Phase 4 tokens (no `jti`) are rejected: "Token missing required identifier"

### RBAC

See Section 8. Centralized in `permissions.py`. Frontend role checks are cosmetic only — backend enforces all authorization.

### Audit Logging

25 event types recorded to `audit_logs` table. Key properties:
- **Append-only**: app never updates or deletes rows
- **Never raises**: `write_audit_event()` swallows all DB exceptions
- **Secrets stripped**: `_sanitise_metadata()` removes keys containing: password, passwd, token, access_token, refresh_token, api_key, apikey, secret, key, hash, credential, encrypted, private, authorization
- **Admin-only access**: `GET /admin/audit-logs` with pagination and filters

### Gemini API Key Security

- Stored as Fernet ciphertext in DB (`encrypted_gemini_api_key` column)
- Encryption key: `GEMINI_ENCRYPTION_KEY` env var (pre-generated Fernet key) or PBKDF2 derivation from `JWT_SECRET_KEY` (dev fallback)
- API responses: return `has_api_key` bool + 8-char masked preview only — **never plaintext**
- Never logged, never in frontend, never in localStorage

### Prompt Injection Defense (5 layers)

Located in `services/security/prompt_injection/`:
- Direct jailbreak detection (`detector.py`, `rules.py`)
- Document injection scanning (`sanitizer.py`)
- Output validation (`validator.py`)
- Security event logging (`logger.py`)

---

## 17. Environment Variables

**Never commit real values. All values configured in `backend/.env`.**

```
# Application
DATABASE_URL=<sqlite:///./data/secure_legal.db>
ENVIRONMENT=<development|production>
ALLOWED_ORIGINS=<comma-separated URLs>

# JWT Authentication
JWT_SECRET_KEY=<generated with: python -c "import secrets; print(secrets.token_hex(48))">
ALGORITHM=<HS256>
ACCESS_TOKEN_EXPIRE_MINUTES=<30>
REVOCATION_ENABLED=<true|false>

# Gemini API Key Encryption
GEMINI_ENCRYPTION_KEY=<generated with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Google Gemini
GEMINI_API_KEY=<obtained from https://aistudio.google.com/app/apikey>
GEMINI_MODEL_NAME=<gemini-2.0-flash>

# RAG Pipeline
RAG_CHUNK_SIZE=<1000>
RAG_CHUNK_OVERLAP=<150>
RAG_TOP_K=<5>
RAG_SIMILARITY_THRESHOLD=<0.35>
RAG_MAX_CONTEXT_CHUNKS=<5>

# Chat History
CHAT_MAX_HISTORY_MESSAGES=<20>
CHAT_MAX_HISTORY_CHARS=<8000>

# File Uploads
MAX_DOCUMENT_SIZE_MB=<10>
MAX_VERIFICATION_SIZE_MB=<10>

# Rate Limiting
RATE_LIMIT_ENABLED=<true>
RATE_LIMIT_LOGIN=<5/minute>
RATE_LIMIT_REGISTER=<10/minute>
RATE_LIMIT_PUBLIC_QUERY=<20/minute>
RATE_LIMIT_RAG_QUERY=<10/minute>
RATE_LIMIT_DOC_UPLOAD=<5/minute>
RATE_LIMIT_DOC_ANALYSIS=<5/minute>
RATE_LIMIT_CHAT_MESSAGE=<20/minute>
RATE_LIMIT_CHAT_CREATE=<20/minute>
```

---

## 18. Current Features

```
[x] User registration (PUBLIC_USER role forced)
[x] User login + JWT issuance
[x] JWT session management (JTI revocation)
[x] Multi-session support + session list UI
[x] Logout (server-side revocation)
[x] Revoke all sessions
[x] Role-based access control (3 tiers)
[x] Professional verification queue (Admin approve/reject)
[x] Public AI Q&A (Tier 1 — Gemini + Free Engine fallback)
[x] Document upload (PDF, DOCX) with file validation
[x] SHA-256 document hashing
[x] Text extraction (pypdf, python-docx)
[x] Chunking (1000 chars, 150 overlap)
[x] Embeddings (all-MiniLM-L6-v2, 384-dim)
[x] Vector storage (FAISS + SQLite)
[x] RAG query (Tier 2 — grounded, owner-scoped)
[x] Semantic search
[x] Document analysis — 8 sections (summary, clauses, risks, missing, entities, etc.)
[x] Persistent chat (general / document / rag modes)
[x] Multi-turn conversation context
[x] Chat history dashboard (grouped Today/Yesterday/Earlier)
[x] Document-linked chat ("Chat with Document" button)
[x] Chat source tracking (chunk citations in messages)
[x] Similar legal case search (academic dataset)
[x] K-Means case clustering
[x] Legal argument + verdict extraction
[x] Rate limiting (all critical endpoints)
[x] Gemini API key per-user encryption + storage
[x] Audit logging (25 event types, append-only, secrets stripped)
[x] Audit log viewer in Admin dashboard
[x] 5-layer prompt injection defense
[x] PII detection + redaction
[x] Admin dashboard (users, verifications, security events, model status)
[x] RAG audit history (compliance)
[x] System benchmarks + compliance report
[x] TinyLlama SLM integration (optional, local CPU inference)
[x] LoRA fine-tuning pipeline (training/ scripts)
[x] Security test suite (197 tests passing)
[x] Admin Analytics API (summary + recent activity + timeseries — 42 tests passing)
[x] Admin Analytics UI (cards, donut charts, line chart, recent activity feed)
[x] Time-series analytics (Today / 7 Days / 30 Days period selector)
```

---

## 19. Current Development Status

```
Current Phase:     COMPLETE — Admin Analytics (Phases 1–5) verified
Current Feature:   N/A — project in maintenance/deployment state
Status:            All 239 automated tests passing; frontend builds clean
Last Major Change: Admin Analytics Phase 5 QA (Sep 2026)
Known Issues:      See Section 20
```

---

## 20. Known Issues

| # | Issue | Impact | Workaround | Planned Fix |
|---|---|---|---|---|
| 1 | In-memory rate limiting resets on server restart | Burst attacks possible in brief window after restart | Acceptable for single-process dev | Swap to Redis storage for production |
| 2 | Static PBKDF2 salt when GEMINI_ENCRYPTION_KEY not set | Dev-only; all installations share same derivation path | Set GEMINI_ENCRYPTION_KEY in production | Always configure GEMINI_ENCRYPTION_KEY in production |
| 3 | No HTTPS enforcement | Credentials transmitted unencrypted on HTTP | Dev only — localhost is acceptable | Configure nginx/Caddy TLS before any internet deployment |
| 4 | SQLite single-writer lock | Cannot scale to multiple Uvicorn workers | Use --workers 1 in dev | Migrate to PostgreSQL for production |
| 5 | UserSession rows accumulate (no cleanup) | Table grows over time | Manual cleanup acceptable in dev | Add scheduled cleanup job for expired sessions |
| 6 | No JWT refresh token | Users must re-login every 30 min | Increase ACCESS_TOKEN_EXPIRE_MINUTES in dev .env | Add POST /auth/refresh endpoint |
| 7 | TestClient + SlowAPI interaction | Rate-limit tests require special fixture patching | conftest.py disable_rate_limiting fixture | No change needed — test design is correct |

---

## 21. Pending Features

### High Priority
- None — all core features implemented

### Medium Priority
- `[ ]` Refresh token endpoint (`POST /auth/refresh`) for better UX
- `[ ]` Production deployment guide (nginx + PostgreSQL + Redis)
- `[ ]` Session cleanup scheduled job

### Low Priority
- `[ ]` Chat export to PDF (`GET /chat/conversations/{id}/export`)
- `[ ]` Admin chat oversight (view all user conversations)
- `[ ]` Email verification on registration
- `[ ]` Password reset flow
- `[ ]` GEMINI_ENCRYPTION_KEY key rotation script (re-encrypt all rows)

---

## 22. Agent Development Rules

### Rule 1 — Inspect Before Editing
Before modifying any code:
1. Read `brain.md` (this file)
2. Read the relevant source files
3. Check existing APIs in `router.py` + relevant router file
4. Check existing models in `models/`
5. Check existing schemas in `schemas/`
6. Understand current data flow

**Never blindly overwrite working code.**

### Rule 2 — Preserve Existing Features
Before marking any task complete, verify these still work:
- Login / Logout / Registration
- Public AI Q&A (Tier 1)
- Professional RAG (Tier 2)
- Document upload + analysis
- Persistent chat (all 3 modes)
- Admin dashboard
- All 197 security tests passing (`python -m pytest tests/ -q`)

### Rule 3 — Reuse Existing Services
Do NOT duplicate:
- `GeminiService` or `get_gemini_api_key()` — already in `gemini_service.py`
- `retrieve_relevant_chunks()` — already in `services/retrieval/retrieval_service.py`
- `write_audit_event()` — already in `services/audit/audit_service.py`
- `FileValidator` — already in `services/document/file_validator.py`
- `get_current_user` / `require_professional` — already in `deps.py` / `permissions.py`

### Rule 4 — Security First
Never:
- Log API keys, JWT secrets, or passwords
- Skip `owner_id` filter on any DB query
- Return full Gemini API key in any API response
- Trust role/permission values from the frontend
- Store secrets in source code (use `.env`)
- Allow cross-user resource access

### Rule 5 — Database Safety
- Never delete or reset the production SQLite database
- Use safe migrations (ALTER TABLE or new column with default)
- Preserve existing user/document data

### Rule 6 — Minimal Changes
- Prefer small, focused, backward-compatible changes
- Do not rewrite components unrelated to the current task

### Rule 7 — Test Before Completion
```bash
cd backend
python -m pytest tests/ -q   # must show 197 passed, 1 skipped

cd frontend
npx vite build --mode development   # must show 0 errors
```

### Rule 8 — Update brain.md
After every code change that affects architecture, APIs, models, features, or security — update the relevant sections of this file in the same task.

---

## 23. Change History

### 2026-09-10

#### Added
- Phase 2: Secure file validation (magic bytes, path traversal, extension whitelist)
- Phase 3: Rate limiting via SlowAPI (all critical endpoints)
- Phase 4: JWT session management (JTI revocation, UserSession model, logout, revoke-all)
- Phase 5: Chat history dashboard (grouped, timestamps, document indicators, typing steps)
- Phase 6: Audit logging (25 event types, append-only, secret sanitisation)
- Phase 7: Gemini API-key security (GEMINI_ENCRYPTION_KEY, masked responses, error sanitisation)
- Persistent chat: document-linked conversations, multi-turn context injection
- Document analysis: 8-section structured output (6 sub-services + Gemini/fallback dual engine)
- Admin Audit Logs tab in AdminDashboard.jsx
- brain.md (this file)

#### Security
- GEMINI_ENCRYPTION_KEY env var for dedicated Fernet key
- gemini_service.py: raw HTTP errors never forwarded to clients
- Audit service: `_sanitise_metadata()` strips all secret-like keys
- Rate limit 429 responses: safe message + Retry-After header
- 197 automated security tests

#### Tests
- test_phase7_security.py: 47 tests (all acceptance criteria)
- test_rbac.py: 64 tests
- test_session_management.py: 19 tests
- test_rate_limiting.py: 28 tests
- test_file_validation.py: 25 tests
- test_chat_security.py: 15 tests
- Total: 197 passed, 1 skipped, 0 failed


---

## 24. Admin Analytics (Phase: Admin Analytics)

### New Endpoints

| Method | Path | Auth | Role | Purpose |
|---|---|---|---|---|
| GET | `/api/v1/admin/analytics/summary` | JWT | Admin | Full analytics: users, docs, AI usage, sessions |
| GET | `/api/v1/admin/analytics/recent-activity` | JWT | Admin | Recent audit events feed (safe fields only) |

### Analytics Service

File: `backend/app/services/analytics/analytics_service.py`

All calculations use SQL `COUNT`/`GROUP BY` — no full-table Python iteration.

| Metric | Source | Method |
|---|---|---|
| Total / public / professional / admin users | `users.role` | `GROUP BY role` |
| New users last 7/30 days | `users.created_at` | `WHERE created_at >= now - N days` |
| Documents total / by status / by type | `legal_documents` | `GROUP BY processing_status`, `GROUP BY document_type` |
| Total AI responses | `chat_messages` | `WHERE role='assistant'` |
| Gemini usage | `chat_messages.model_used` | `WHERE model_used='gemini'` |
| Fallback usage | `chat_messages.model_used` | `WHERE model_used='free-legal-engine'` |
| Total RAG queries | `rag_audit_logs` | `COUNT(*)` |
| Conversations by mode | `conversations.mode` | `GROUP BY mode` |
| Active sessions | `user_sessions` | `WHERE revoked_at IS NULL AND expires_at > now` |
| Recent activity | `audit_logs` | `ORDER BY created_at DESC LIMIT n` |

### Security
- Both endpoints require `ADMIN` role — enforced in FastAPI via `require_roles(UserRole.ADMIN)`
- No passwords, tokens, keys, or document content in any response
- All sub-functions catch exceptions independently — analytics failure never crashes the app


### Admin Analytics UI (Phase 3 — Frontend)

**New component:** `frontend/src/components/AnalyticsTab.jsx`

Renders inside `AdminDashboard.jsx` when the **Analytics** tab is active.

| Section | What it shows |
|---|---|
| User cards | Total, Public, Professionals, New (7 days) — with horizontal progress bars |
| Doc + AI cards | Documents, AI Responses, RAG Queries, Active Sessions |
| Provider cards | Gemini Requests + Fallback Requests with proportion bars |
| User donut chart | Public / Professional / Admin distribution (pure SVG) |
| AI donut chart | Gemini % vs Fallback % (pure SVG) |
| Recent Activity | Event type badge, user email, resource, OK/FAIL, relative timestamp |

**States handled:** loading skeleton (pulse animation), error message, empty state ("No recent activity"), Refresh button.

**No new dependencies** — charts built with inline SVG + TailwindCSS.

**File changes:**
- `frontend/src/components/AnalyticsTab.jsx` — **created**
- `frontend/src/pages/AdminDashboard.jsx` — added `AnalyticsTab` import, analytics state vars, `fetchAnalytics()`, tab button, tab panel


### Admin Analytics Phase 4 — Time-Series (added)

**New backend endpoint:** `GET /api/v1/admin/analytics/timeseries?days=N` (Admin only)

- `days` param: 1 (today), 7 (default), 30 — validated 1–30 by FastAPI
- Returns an array of per-day entries, one per calendar day, oldest→newest
- Each entry: `{ date, users, documents, ai_total, gemini, fallback }`
- Zero-filled for days with no activity (no gaps for frontend)
- Uses `ChatMessage.created_at`, `LegalDocument.created_at`, `User.created_at`

**New frontend component:** `frontend/src/components/TimeseriesChart.jsx`

- Period selector: Today / 7 Days / 30 Days
- Metric toggles (click to show/hide): AI Responses, Gemini, Fallback, Documents, New Users
- Pure SVG polyline chart (no new npm dependencies)
- Hover tooltip showing all active metric values for that day
- Loading spinner overlay, error state, empty state

**Tests:** 42/42 passing (20 new timeseries tests added to `test_analytics.py`)


---

## 25. Admin Analytics — Phase 5 Final QA (Verified)

**QA Date:** September 2026  
**Test result:** 239 passed, 1 skipped, 0 failed  
**Frontend build:** 1491 modules, 0 errors

### Data Accuracy Verification (against live DB)

| Metric | DB direct count | Service output | Match |
|---|---|---|---|
| Total users | 12 | 12 | ✅ PASS |
| Public users | 9 | 9 | ✅ PASS |
| Professionals | 2 | 2 | ✅ PASS |
| Admins | 1 | 1 | ✅ PASS |
| Documents | 4 | 4 | ✅ PASS |
| AI total responses | 2 | 2 | ✅ PASS |
| Gemini responses | 0 | 0 | ✅ PASS |
| Fallback responses | 2 | 2 | ✅ PASS |
| RAG queries | 0 | 0 | ✅ PASS |

### Security Verification

| Scenario | Expected | Result |
|---|---|---|
| Unauthenticated → /analytics/summary | 401/403 | ✅ PASS |
| Public user → /analytics/summary | 403 | ✅ PASS |
| Professional → /analytics/summary | 403 | ✅ PASS |
| Admin → /analytics/summary | 200 | ✅ PASS |
| Unauthenticated → /analytics/timeseries | 401/403 | ✅ PASS |
| Public user → /analytics/timeseries | 403 | ✅ PASS |
| Professional → /analytics/timeseries | 403 | ✅ PASS |
| Admin → /analytics/timeseries | 200 | ✅ PASS |
| Summary response contains "password" | Not present | ✅ PASS |
| Summary response contains "api_key" | Not present | ✅ PASS |
| Summary response contains "token" | Not present | ✅ PASS |
| Summary response contains "secret" | Not present | ✅ PASS |

### Performance Verification

All `analytics_service.py` queries use SQL aggregation (`func.count`, `GROUP BY`, bulk `IN`). Zero N+1 patterns. Timeseries fetches only timestamp + model columns with date range filter. Confirmed by code inspection (18 db.query calls audited).

### Analytics Endpoints Summary

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/v1/admin/analytics/summary` | Admin | Users, docs, AI, sessions — all SQL COUNT/GROUP BY |
| `GET /api/v1/admin/analytics/recent-activity?limit=N` | Admin | Last N audit events (safe fields only) |
| `GET /api/v1/admin/analytics/timeseries?days=N` | Admin | Per-day data for 1/7/30 days — zero-filled |

### UI Components

| Component | File | Status |
|---|---|---|
| Analytics tab panel | `AnalyticsTab.jsx` | ✅ Verified |
| Time-series line chart | `TimeseriesChart.jsx` | ✅ Verified |
| Period selector | Inside `TimeseriesChart.jsx` | ✅ Today / 7 Days / 30 Days |
| Metric toggles | Inside `TimeseriesChart.jsx` | ✅ 5 toggleable metrics |
| Loading skeleton | `AnalyticsTab.jsx` | ✅ Animated pulse |
| Error state | `AnalyticsTab.jsx` | ✅ "Unable to load analytics." |
| Empty state | Charts + activity | ✅ "No recent activity." / "No data available." |
| Refresh button | `AnalyticsTab.jsx` | ✅ Reloads all three endpoints |
| Hover tooltip | `TimeseriesChart.jsx` | ✅ SVG overlay, all active metrics |

### Test Coverage

| File | Tests | Status |
|---|---|---|
| `test_analytics.py` | 42 | ✅ All pass |
| `test_phase7_security.py` | 47 | ✅ All pass |
| `test_rbac.py` | 64 | ✅ All pass |
| `test_session_management.py` | 19 | ✅ 18 pass, 1 skip |
| `test_rate_limiting.py` | 28 | ✅ All pass |
| `test_file_validation.py` | 25 | ✅ All pass |
| `test_chat_security.py` | 15 | ✅ All pass |
| **TOTAL** | **240** | **239 pass, 1 skip, 0 fail** |

### Known Limitations (Analytics-specific)

| Limitation | Impact | Note |
|---|---|---|
| Timeseries data is sparse at project start | All zeros for days before first usage | Expected — no historical data to backfill |
| `gemini=0` in current DB | No Gemini key configured → all AI used fallback engine | Set `GEMINI_API_KEY` in `.env` to use Gemini |
| SQLite single-writer | In-memory rate-limiter resets on restart | Production: switch to PostgreSQL + Redis |

### Change History Entry

#### 2026-09-20 — Admin Analytics Phases 1–5

**Added:**
- `backend/app/services/analytics/analytics_service.py` — summary + timeseries calculations
- `GET /api/v1/admin/analytics/summary` — users, docs, AI, sessions
- `GET /api/v1/admin/analytics/recent-activity` — audit event feed
- `GET /api/v1/admin/analytics/timeseries?days=N` — per-day time-series (1/7/30)
- `frontend/src/components/AnalyticsTab.jsx` — cards, donut charts, activity feed
- `frontend/src/components/TimeseriesChart.jsx` — SVG line chart, period selector, metric toggles
- Analytics tab in AdminDashboard
- 42 automated analytics tests

**Verified:**
- All 9 metrics match actual database values exactly
- Admin-only access enforced at backend (FastAPI `require_roles(ADMIN)`)
- No secrets (passwords, keys, tokens) in any analytics response
- All SQL uses COUNT/GROUP BY — no N+1 queries
- 239/240 automated tests passing (1 skipped — cross-user integration test)
- Frontend: 1491 modules, 0 build errors
