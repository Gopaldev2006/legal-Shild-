# System Architecture & Flow Verification

## 1. Executive Summary

The **Secure AI Assistant for Legal Data Analysis** is a security-first AI platform engineered for high-consequence legal data processing. It enforces strict RBAC, multi-layered prompt injection defense, owner-isolated vector retrieval, local SLM inference, citation verification, and a tamper-evident audit log.

---

## 2. Complete End-to-End System Pipeline

```
USER
  │
  ├──► [1] Registration / Login (JWT Auth + bcrypt password hashing)
  │
  ├──► [2] Role Determination & RBAC Enforcement
  │         ├── PUBLIC_USER (General Legal Q&A, Disclaimer, No Document Access)
  │         └── LEGAL_PROFESSIONAL
  │               ├── UNVERIFIED (Restricted: Blocked from RAG & Corpus)
  │               └── VERIFIED (Full Access after Admin Bar Council Approval)
  │
  ├──► [3] Document Upload & Ingestion Pipeline
  │         ├── File Type Validation (.pdf, .txt, .docx, max 10MB)
  │         ├── Text Extraction (PyMuPDF / docx)
  │         ├── Text Chunking (Recursive Character Text Splitter - 500 chars, 50 overlap)
  │         ├── Vector Embedding Generation (SentenceTransformers: all-MiniLM-L6-v2)
  │         └── Secure Vector Storage (FAISS Index + Owner-ID Metadata Indexing)
  │
  ├──► [4] Secure Retrieval & AI Reasoning Pipeline (RAG)
  │         ├── Permission-Aware Pre-Filtering (Enforces owner_id == current_user.id)
  │         ├── Case Retrieval & Clustering (TF-IDF + Cosine Similarity / K-Means)
  │         ├── 5-Layer Prompt Injection Firewall
  │         │     ├── Layer 1: Heuristic Keyword & Injection Pattern Filter
  │         │     ├── Layer 2: Regex & Delimiter Attack Sanitizer
  │         │     ├── Layer 3: System Prompt Leakage & Extraction Defense
  │         │     ├── Layer 4: Strict Context Delimiter Enclosure (`<context>` tags)
  │         │     └── Layer 5: PII Masking & Sensitive Data Filtering
  │         ├── Local SLM Inference (TinyLlama-1.1B / Mock Mode Fallback)
  │         ├── Decoupled Citation Verification (Cross-verifies claims against retrieved chunks)
  │         └── Output Security Validation (Filters out malicious payload leakage)
  │
  └──► [5] Tamper-Evident Audit Logging
            └── Hash-Chain Ledger (SHA-256 linked blocks: index, timestamp, user_id, action, hash, prev_hash)
```

---

## 3. Detailed Data & Workflow Security Matrix

| Flow | Role Required | Permission Checks | Document Scope | RAG Access | Audit Action Logged |
|---|---|---|---|---|---|
| **Public Q&A** | `PUBLIC_USER` | Valid JWT | None | Denied | `PUBLIC_QUERY` |
| **Verification Submit** | `LEGAL_PROFESSIONAL` | Valid JWT | Upload Bar ID / Credential | Denied | `VERIFICATION_SUBMITTED` |
| **Admin Approval** | `ADMIN` | Valid JWT + `ADMIN` role | View All Requests | N/A | `VERIFICATION_APPROVED` |
| **Document Upload** | `VERIFIED` Professional | Valid JWT + `VERIFIED` status | Private (Owner Isolation) | Enabled | `DOCUMENT_UPLOADED` |
| **Professional RAG** | `VERIFIED` Professional | Valid JWT + `VERIFIED` status | Restricted to `user_id` docs | Enabled | `RAG_QUERY` |
| **Audit Verification** | `ADMIN` | Valid JWT + `ADMIN` role | Full Audit Hash Chain | N/A | `AUDIT_VERIFIED` |

---

## 4. Key Security Guarantees

1. **Strict Owner Pre-Filtering**: Vector search query never scans outside the authenticated `user_id`'s documents.
2. **Untrusted Upload Handling**: Text extracted from uploaded files is isolated inside XML context delimiters and never evaluated as executable code or system instructions.
3. **Decoupled Citation Verification**: Post-processing step validates every cited passage ID directly against the source text to prevent AI hallucinations.
4. **Tamper-Evident Audit Trail**: Every critical action generates a cryptographically hashed log block (`hash = SHA256(index + timestamp + action + details + prev_hash)`). Any manual modification breaks the chain verification.
