# Security Architecture & Threat Defenses

## 1. Security Overview

The **Secure AI Assistant for Legal Data Analysis** enforces a multi-layered, zero-trust security model. Security protections are strictly divided into pre-generation filters, untrusted data isolation barriers, cryptographic audit trails, and post-generation output validation.

---

## 2. The 5-Layer Prompt Injection Firewall

```text
[Incoming User Query]
         │
         ▼
[Layer 1: Input Sanitization & Direct Jailbreak Detection]
  - Scans for instruction overrides ("IGNORE PREVIOUS INSTRUCTIONS")
  - Scans for roleplay bypasses ("You are DAN", "Developer mode")
         │
         ▼
[Layer 2: Pre-Generation Permission-Aware Vector Filtering]
  - Vector search pre-filters chunks by owner_id == current_user.id
  - Unauthorized chunks are purged BEFORE prompt assembly
         │
         ▼
[Layer 3: Untrusted Data Isolation & XML Enclosure]
  - Document chunks encapsulated in strict <retrieved_context> tags
  - Document instructions CANNOT override system prompt directives
         │
         ▼
[Layer 4: Indirect Document Injection Scanner]
  - Scans retrieved context text for embedded prompt injection payloads
         │
         ▼
[Layer 5: Post-Generation Output Validation & PII Redaction]
  - Redacts PII (SSN, Aadhar, Credit Cards) & system prompt leaks
```

---

## 3. Two-Tier Access Scope Enforcer

| Role Scope | Status | Allowed Endpoints | Disallowed Operations |
| :--- | :--- | :--- | :--- |
| `PUBLIC_USER` | `UNVERIFIED` | General Q&A (`/rag/public-query`), Auth, Health | RAG, Uploads, FAISS Vector Search, Audit Logs |
| `LEGAL_PROFESSIONAL` | `UNVERIFIED` / `PENDING` | Public Q&A, Upload Verification Card | Professional RAG, Document Storage, Precedent Search |
| `LEGAL_PROFESSIONAL` | `VERIFIED` | Full RAG, Upload Documents, Precedent Search, Clusters | Admin Administration Router (`/admin/*`) |
| `ADMIN` | `VERIFIED` | Full Admin Center, Verification Queue, Security Audit | Restricted from viewing non-owned private context text |

---

## 4. Cryptographic Hashing & Audit Log Immutability

1. **SHA-256 Hashing**:
   - Computes SHA-256 cryptographic hashes for every uploaded file upon ingestion.
   - Hashes are stored in database records to enable tamper verification during inspection.

2. **Security Threat Audit Database**:
   - Timestamped records created for every direct injection attempt, indirect document injection attempt, PII redaction event, and unauthorized matter access refusal.
   - Logs store event type, severity level (`CRITICAL`, `HIGH`, `MEDIUM`), user ID, and sanitized snippet previews.
