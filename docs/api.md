# REST API Documentation

**Base URL:** `http://127.0.0.1:8000/api/v1`  
**Authentication:** Bearer HTTP Header (`Authorization: Bearer <access_token>`)

---

## 1. Authentication Endpoints (`/api/v1/auth`)

### `POST /api/v1/auth/register`
- **Description:** Registers a new user account. Forces `PUBLIC_USER` role scope.
- **Request Body:**
  ```json
  {
    "name": "Adv. Sharma",
    "email": "user@example.com",
    "password": "password123"
  }
  ```
- **Response (HTTP 201 Created):**
  ```json
  {
    "id": 1,
    "name": "Adv. Sharma",
    "email": "user@example.com",
    "role": "PUBLIC_USER",
    "verification_status": "UNVERIFIED"
  }
  ```

### `POST /api/v1/auth/login`
- **Description:** Authenticates user and returns JWT access token.
- **Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "password123"
  }
  ```
- **Response (HTTP 200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "name": "Adv. Sharma",
      "email": "user@example.com",
      "role": "PUBLIC_USER",
      "verification_status": "UNVERIFIED"
    }
  }
  ```

---

## 2. Professional Identity Verification (`/api/v1/verification`)

### `POST /api/v1/verification/request`
- **Description:** Submits Bar Council license or legal credential for verification.
- **Headers:** `Authorization: Bearer <token>`
- **Form Data:** `file` (PDF, PNG, JPG, WEBP, TXT up to 10MB)
- **Response (HTTP 200 OK):**
  ```json
  {
    "id": 1,
    "status": "PENDING",
    "message": "Verification request submitted successfully"
  }
  ```

---

## 3. Document Management (`/api/v1/documents`)

### `POST /api/v1/documents/upload`
- **Description:** Uploads, cleans, and chunks a legal document. Scope assigned to current user.
- **Headers:** `Authorization: Bearer <token>` (Requires `VERIFIED` status)
- **Form Data:** `file`, `document_type`, `jurisdiction` (optional), `matter_id` (optional)
- **Response (HTTP 200 OK):**
  ```json
  {
    "id": 10,
    "filename": "contract.pdf",
    "file_hash": "a591a6d40bf...",
    "chunk_count": 8,
    "processing_status": "COMPLETED"
  }
  ```

### `GET /api/v1/documents/`
- **Description:** Lists authorized legal documents owned by current user.
- **Response (HTTP 200 OK):** Array of document metadata items.

### `DELETE /api/v1/documents/{id}`
- **Description:** Deletes owned document and purges text chunks from vector index.

---

## 4. RAG Engine & Legal Chat (`/api/v1/rag`)

### `POST /api/v1/rag/public-query`
- **Description:** General legal educational Q&A for Tier 1 public users. Zero document access.
- **Request Body:** `{"query": "What is Habeas Corpus?"}`
- **Response (HTTP 200 OK):**
  ```json
  {
    "answer": "Habeas corpus is a fundamental legal writ...",
    "disclaimer": "Legal Disclaimer: Educational information only.",
    "is_safe": true
  }
  ```

### `POST /api/v1/rag/query`
- **Description:** Permission-aware RAG query over authorized case files for Tier 2 Verified Professionals.
- **Headers:** `Authorization: Bearer <token>`
- **Request Body:**
  ```json
  {
    "query": "Analyze indemnity obligations under Section 14",
    "matter_id": "CAS-2026-901",
    "provider_type": "local",
    "top_k": 5
  }
  ```
- **Response (HTTP 200 OK):**
  ```json
  {
    "answer": "Under Section 14 of the contract...",
    "provider_used": "Local SLM Engine",
    "chunks_retrieved": 4,
    "citations": [
      {
        "document_id": 10,
        "document_name": "contract.pdf",
        "page": 3,
        "chunk_id": "chk_10_2_a1b2c3d4",
        "relevance": 0.94,
        "snippet": "Tenant shall indemnify Landlord..."
      }
    ],
    "is_safe": true
  }
  ```

### `POST /api/v1/rag/extract-arguments/{document_id}`
- **Description:** Extracts cited statutes, primary contentions, and verdict summary from authorized document.

### `GET /api/v1/rag/audit-history`
- **Description:** Returns user's query execution audit history trail.

---

## 5. Case Retrieval & Clustering (`/api/v1/cases`)

### `POST /api/v1/cases/search`
- **Description:** Semantic similarity search across public academic precedent judgments.

### `POST /api/v1/cases/clusters/generate`
- **Description:** Triggers K-Means clustering algorithm over legal precedent vector embeddings.

---

## 6. Admin Management Router (`/api/v1/admin`)

- `GET /api/v1/admin/dashboard-summary`: Returns metric card totals, memory status, model details.
- `GET /api/v1/admin/users`: Paginated user list with role & verification filtering.
- `GET /api/v1/admin/verifications`: List pending professional verification requests.
- `POST /api/v1/admin/verifications/{id}/approve`: Approves verification and elevates user role.
- `POST /api/v1/admin/verifications/{id}/reject`: Rejects request with review notes.
- `GET /api/v1/admin/documents`: System-wide document audit list.
- `GET /api/v1/admin/security-events`: Security threat event log audit.
- `GET /api/v1/admin/model-status`: Active SLM parameters and LoRA PEFT status.
