"""
Document Upload & Processing API
=================================
Pipeline:  Upload → PROCESSING → CHUNKING → READY  (or FAILED)

Ownership chain enforced on every endpoint:
    current_user.id → LegalDocument.owner_id → DocumentChunk.owner_id
"""
import os
import uuid
import hashlib
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User, UserRole
from app.models.document import LegalDocument, DocumentChunk, ProcessingStatus, DocumentType
from app.schemas.document import (
    DocumentResponse, ChunkResponse, DocumentAnalysisResponse,
    StructuredSummarySchema, SummarySourceSchema,
    ImportantClauseSchema, ObligationSchema, ClauseSourceSchema,
    RiskAssessmentSchema, IdentifiedRiskSchema, RiskSourceSchema,
    MissingAmbiguousAnalysisSchema, MissingClauseSchema,
    AmbiguousClauseSchema, AmbiguousClauseSourceSchema,
    ConflictingProvisionSchema,
    EntitiesAnalysisSchema, PartySchema, KeyDateSchema,
    SourceReferenceSchema, EvidenceSchema,
)
from app.services.document.extractor import extract_text_from_document
from app.services.document.chunker import create_chunks
from app.services.embedding.embedding_service import EmbeddingService
from app.services.document.document_analysis_service import analyze_document
from app.services.document.file_validator import FileValidator, FileValidationError
from app.services.audit.audit_service import write_audit_event
from app.models.audit_log import AuditEventType
from app.core.limiter import limiter
from app.core.config import settings as app_settings

logger = logging.getLogger(__name__)

router = APIRouter()

DOC_STORAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "documents")
)
os.makedirs(DOC_STORAGE_DIR, exist_ok=True)


def _client_ip(request: Request):
    return request.client.host if request.client else None


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_doc_or_404(document_id: int, db: Session) -> LegalDocument:
    doc = db.query(LegalDocument).filter(LegalDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def _assert_owner(doc: LegalDocument, current_user: User) -> None:
    if doc.owner_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: you do not have access to this document",
        )


def _chunk_count(doc_id: int, db: Session) -> int:
    return db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).count()


def _embedded_count(doc_id: int, db: Session) -> int:
    return (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == doc_id, DocumentChunk.is_embedded == True)
        .count()
    )


def _build_response(doc: LegalDocument, db: Session) -> DocumentResponse:
    resp                = DocumentResponse.model_validate(doc)
    resp.chunk_count    = _chunk_count(doc.id, db)
    resp.embedded_count = _embedded_count(doc.id, db)
    return resp


def _run_pipeline(doc: LegalDocument, current_user: User, db: Session) -> None:
    """
    Full document processing pipeline:

    UPLOADING  →  PROCESSING  →  CHUNKING  →  EMBEDDING  →  READY
                                                          ↘  FAILED

    Steps
    -----
    1. PROCESSING  — extract raw text from PDF / DOCX / TXT
    2. CHUNKING    — delete old chunks, create fresh legal-aware chunks
    3. EMBEDDING   — generate float32 embeddings (batch=32), store as base64
    4. READY       — all chunks embedded and validated
    5. FAILED      — safe error stored on any exception (no internals exposed)
    """
    try:
        # ── Step 1: Text extraction ───────────────────────────────────────
        doc.processing_status = ProcessingStatus.PROCESSING
        db.add(doc); db.commit()

        pages = extract_text_from_document(doc.stored_path, doc.file_type)

        # ── Step 2: Delete old chunks, create new ones ────────────────────
        doc.processing_status = ProcessingStatus.CHUNKING
        db.add(doc); db.commit()

        (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc.id)
            .delete(synchronize_session="fetch")
        )
        db.commit()

        doc_metadata = {
            "doc_id":        doc.id,
            "filename":      doc.filename,
            "document_type": doc.document_type.value,
            "jurisdiction":  doc.jurisdiction,
            "matter_id":     doc.matter_id,
        }
        chunk_dicts = create_chunks(pages, doc_metadata)

        chunk_objects = [
            DocumentChunk(
                chunk_id=        chk["chunk_id"],
                document_id=     doc.id,
                owner_id=        current_user.id,
                matter_id=       doc.matter_id,
                text=            chk["text"],
                page_number=     chk["page_number"],
                chunk_index=     chk["chunk_index"],
                start_char=      chk.get("start_char"),
                end_char=        chk.get("end_char"),
                token_count=     chk.get("token_count"),
                source_metadata= chk["source_metadata"],
                is_embedded=     False,
            )
            for chk in chunk_dicts
        ]
        db.add_all(chunk_objects)
        db.commit()
        # Refresh to get DB-assigned IDs
        for obj in chunk_objects:
            db.refresh(obj)

        # ── Step 3: Embed chunks ──────────────────────────────────────────
        doc.processing_status = ProcessingStatus.EMBEDDED
        db.add(doc); db.commit()

        emb_svc = EmbeddingService.get()
        texts   = [c.text for c in chunk_objects]
        vectors = emb_svc.embed_batch(texts)   # list[ndarray | None]

        embedded_count = 0
        for chunk_obj, vec in zip(chunk_objects, vectors):
            if vec is None:
                logger.warning(
                    "Chunk %s skipped (empty text) — no embedding stored",
                    chunk_obj.chunk_id,
                )
                continue
            if not emb_svc.validate_embedding(vec):
                logger.warning(
                    "Chunk %s failed embedding validation", chunk_obj.chunk_id
                )
                continue
            chunk_obj.embedding     = emb_svc.to_storage(vec)
            chunk_obj.embedding_dim = emb_svc.dimension
            chunk_obj.is_embedded   = True
            db.add(chunk_obj)
            embedded_count += 1

        db.commit()

        # ── Step 4: Mark READY ────────────────────────────────────────────
        doc.processing_status = ProcessingStatus.READY
        doc.error_message     = None
        db.add(doc); db.commit()
        db.refresh(doc)

        logger.info(
            "Document #%d ready: %d chunks, %d embedded (dim=%d)",
            doc.id, len(chunk_objects), embedded_count, emb_svc.dimension,
        )

    except Exception as exc:
        db.rollback()
        safe_msg = f"Processing failed: {type(exc).__name__}"
        logger.exception("Pipeline error for document #%d", doc.id)
        doc.processing_status = ProcessingStatus.FAILED
        doc.error_message     = safe_msg
        db.add(doc); db.commit()
        db.refresh(doc)


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Legal Document (PDF / DOCX)",
)
@limiter.limit(lambda: app_settings.RATE_LIMIT_DOC_UPLOAD)
async def upload_legal_document(
    request:       Request,
    file:          UploadFile         = File(...),
    document_type: DocumentType       = Form(DocumentType.GENERAL),
    jurisdiction:  Optional[str]      = Form(None),
    matter_id:     Optional[str]      = Form(None),
    current_user:  User               = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db:            Session            = Depends(get_db),
):
    """
    Upload → validate → store → PROCESSING → CHUNKING → READY.
    Restricted to VERIFIED LEGAL PROFESSIONAL or ADMIN.
    """
    # ── Secure file validation (Phase 2) ────────────────────────────────────
    # Read content first so validation and hashing share the same bytes.
    content = await file.read()
    try:
        ext = FileValidator.validate(
            filename=file.filename,
            content=content,
            max_size_mb=settings.MAX_DOCUMENT_SIZE_MB,
        )
    except FileValidationError as fve:
        raise HTTPException(status_code=fve.http_status, detail=str(fve))

    # Keep the original filename as metadata only; never use it for storage.
    filename      = file.filename or f"document{ext}"

    file_hash     = hashlib.sha256(content).hexdigest()
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    saved_path    = os.path.join(DOC_STORAGE_DIR, safe_filename)

    with open(saved_path, "wb") as fh:
        fh.write(content)

    doc = LegalDocument(
        owner_id=         current_user.id,
        filename=         filename,
        stored_filename=  safe_filename,
        stored_path=      saved_path,
        file_type=        ext.strip("."),
        file_size=        len(content),
        file_hash=        file_hash,
        document_type=    document_type,
        jurisdiction=     jurisdiction.strip() if jurisdiction else None,
        matter_id=        matter_id.strip()    if matter_id    else None,
        processing_status=ProcessingStatus.UPLOADING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    _run_pipeline(doc, current_user, db)
    # Audit: DOCUMENT_UPLOADED
    write_audit_event(
        db=db, event_type=AuditEventType.DOCUMENT_UPLOADED,
        user_id=current_user.id, resource_type="document", resource_id=doc.id,
        success=True, ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"filename": filename, "file_type": ext.strip("."), "size_bytes": len(content)},
    )
    return _build_response(doc, db)


@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentResponse,
    summary="Re-run extraction + chunking on an existing document",
)
def reprocess_document(
    document_id:  int,
    current_user: User    = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db:           Session = Depends(get_db),
):
    """
    Deletes existing chunks for this document and re-runs the full pipeline.
    Safe: never touches chunks belonging to other documents.
    """
    doc = _get_doc_or_404(document_id, db)
    _assert_owner(doc, current_user)

    if not os.path.exists(doc.stored_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical file missing — cannot reprocess",
        )

    _run_pipeline(doc, current_user, db)
    return _build_response(doc, db)


@router.get(
    "/",
    response_model=List[DocumentResponse],
    summary="List authorized legal documents",
)
def list_documents(
    current_user: User    = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db:           Session = Depends(get_db),
):
    if current_user.role == UserRole.ADMIN:
        docs = db.query(LegalDocument).order_by(LegalDocument.created_at.desc()).all()
    else:
        docs = (
            db.query(LegalDocument)
            .filter(LegalDocument.owner_id == current_user.id)
            .order_by(LegalDocument.created_at.desc())
            .all()
        )

    results = []
    for doc in docs:
        results.append(_build_response(doc, db))
    return results


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata & processing status",
)
def get_document_details(
    document_id:  int,
    current_user: User    = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db:           Session = Depends(get_db),
):
    doc = _get_doc_or_404(document_id, db)
    _assert_owner(doc, current_user)
    # Audit: DOCUMENT_ACCESSED
    write_audit_event(
        db=db, event_type=AuditEventType.DOCUMENT_ACCESSED,
        user_id=current_user.id, resource_type="document", resource_id=doc.id,
        success=True, metadata={"filename": doc.filename},
    )
    return _build_response(doc, db)


@router.get(
    "/{document_id}/chunks",
    response_model=List[ChunkResponse],
    summary="Get text chunks for a document",
)
def get_document_chunks(
    document_id:  int,
    current_user: User    = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db:           Session = Depends(get_db),
):
    doc = _get_doc_or_404(document_id, db)
    _assert_owner(doc, current_user)

    # Authorization via owner_id — never rely on document_id alone
    chunks = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.owner_id    == current_user.id
            if current_user.role != UserRole.ADMIN
            else DocumentChunk.document_id == document_id,
        )
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    return chunks


@router.get(
    "/{document_id}/download",
    summary="Secure document file download",
)
def download_document_file(
    document_id:  int,
    current_user: User    = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db:           Session = Depends(get_db),
):
    doc = _get_doc_or_404(document_id, db)
    _assert_owner(doc, current_user)

    if not os.path.exists(doc.stored_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical file missing",
        )

    return FileResponse(
        path=      doc.stored_path,
        filename=  doc.filename,
        media_type="application/octet-stream",
    )


@router.delete(
    "/{document_id}",
    summary="Delete document, all its chunks, and the physical file",
)
def delete_document(
    document_id:  int,
    current_user: User    = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db:           Session = Depends(get_db),
):
    doc = _get_doc_or_404(document_id, db)
    _assert_owner(doc, current_user)

    if os.path.exists(doc.stored_path):
        try:
            os.remove(doc.stored_path)
        except OSError:
            pass

    db.delete(doc)   # cascade deletes chunks via relationship
    db.commit()
    # Audit: DOCUMENT_DELETED
    write_audit_event(
        db=db, event_type=AuditEventType.DOCUMENT_DELETED,
        user_id=current_user.id, resource_type="document", resource_id=document_id,
        success=True, metadata={"filename": doc.filename},
    )
    return {"message": f"Document '{doc.filename}' deleted successfully"}


@router.post(
    "/{document_id}/analyze",
    response_model=DocumentAnalysisResponse,
    summary="Document Analysis Engine — 8-section structured legal analysis",
)
@limiter.limit(lambda: app_settings.RATE_LIMIT_DOC_ANALYSIS)
def analyze_legal_document(
    request:      Request,
    document_id:  int,
    current_user: User    = Depends(require_roles(UserRole.LEGAL_PROFESSIONAL, UserRole.ADMIN)),
    db:           Session = Depends(get_db),
):
    """
    Produces a structured 8-section analysis of the document:
    Summary, Important Clauses, Risks, Missing/Ambiguous Clauses,
    Key Dates, Parties, Obligations, Evidence/Citations.

    Uses Gemini AI if a valid key is configured, otherwise falls back
    to the built-in rule-based analysis engine.

    Security: only the document owner (or ADMIN) can request analysis.
    """
    # Ownership check
    doc = _get_doc_or_404(document_id, db)
    _assert_owner(doc, current_user)

    if doc.processing_status.value not in ("READY", "COMPLETED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document is not ready for analysis (status: {doc.processing_status.value}). "
                   "Please wait for processing to complete.",
        )

    result = analyze_document(
        document_id= document_id,
        user_id=     current_user.id,
        user_role=   current_user.role.value,
        db=          db,
    )

    # Build structured_summary schema if present
    structured_summary_schema = None
    if result.structured_summary:
        ss = result.structured_summary
        structured_summary_schema = StructuredSummarySchema(
            executive_summary= ss.executive_summary,
            document_type=     ss.document_type,
            purpose=           ss.purpose,
            main_subject=      ss.main_subject,
            key_takeaways=     ss.key_takeaways,
            sources=           [
                SummarySourceSchema(page_number=s.page_number, chunk_id=s.chunk_id)
                for s in ss.sources
            ],
            provider_used=     ss.provider_used,
        )

    # Build structured_clauses and structured_obligations schemas if present
    structured_clauses_schema = None
    structured_obligations_schema = None
    if result.clause_analysis:
        ca = result.clause_analysis
        structured_clauses_schema = [
            ImportantClauseSchema(
                clause_type= c.clause_type,
                title=       c.title,
                description= c.description,
                importance=  c.importance,
                source=      ClauseSourceSchema(
                    page_number= c.source.page_number,
                    chunk_id=    c.source.chunk_id,
                )
            )
            for c in ca.clauses
        ]
        structured_obligations_schema = [
            ObligationSchema(
                party=      o.party,
                obligation= o.obligation,
                deadline=   o.deadline,
                source=     ClauseSourceSchema(
                    page_number= o.source.page_number,
                    chunk_id=    o.source.chunk_id,
                )
            )
            for o in ca.obligations
        ]

    # Build structured_risk_assessment schema if present
    structured_risk_assessment_schema = None
    if result.risk_assessment:
        ra = result.risk_assessment
        structured_risk_assessment_schema = RiskAssessmentSchema(
            overall_risk=  ra.overall_risk,
            risk_score=    ra.risk_score,
            factors=       ra.factors,
            risks=         [
                IdentifiedRiskSchema(
                    category=    r.category,
                    severity=    r.severity,
                    title=       r.title,
                    description= r.description,
                    reason=      r.reason,
                    evidence=    r.evidence,
                    confidence=  r.confidence,
                    source=      RiskSourceSchema(
                        page_number= r.source.page_number,
                        chunk_id=    r.source.chunk_id,
                    )
                )
                for r in ra.risks
            ],
            provider_used= ra.provider_used,
        )

    # Build structured_missing_ambiguous schema if present
    structured_missing_ambiguous_schema = None
    if result.missing_ambiguous_analysis:
        ma = result.missing_ambiguous_analysis
        structured_missing_ambiguous_schema = MissingAmbiguousAnalysisSchema(
            document_type=            ma.document_type,
            document_type_confidence= ma.document_type_confidence,
            missing_clauses= [
                MissingClauseSchema(
                    clause=      mc.clause,
                    status=      mc.status,
                    importance=  mc.importance,
                    explanation= mc.explanation,
                    confidence=  mc.confidence,
                )
                for mc in ma.missing_clauses
            ],
            ambiguous_clauses= [
                AmbiguousClauseSchema(
                    issue_type=              ac.issue_type,
                    clause=                  ac.clause,
                    text=                    ac.text,
                    explanation=             ac.explanation,
                    suggested_clarification= ac.suggested_clarification,
                    source= AmbiguousClauseSourceSchema(
                        page_number= ac.source.page_number,
                        chunk_id=    ac.source.chunk_id,
                    )
                )
                for ac in ma.ambiguous_clauses
            ],
            conflicts= [
                ConflictingProvisionSchema(
                    issue_type=  cp.issue_type,
                    clause=      cp.clause,
                    text_1=      cp.text_1,
                    text_2=      cp.text_2,
                    explanation= cp.explanation,
                    source_1= AmbiguousClauseSourceSchema(
                        page_number= cp.source_1.page_number,
                        chunk_id=    cp.source_1.chunk_id,
                    ),
                    source_2= AmbiguousClauseSourceSchema(
                        page_number= cp.source_2.page_number,
                        chunk_id=    cp.source_2.chunk_id,
                    )
                )
                for cp in ma.conflicts
            ],
            provider_used= ma.provider_used,
        )

    # Build structured_entities schema if present
    structured_entities_schema = None
    if result.entities_analysis:
        ea = result.entities_analysis
        structured_entities_schema = EntitiesAnalysisSchema(
            parties= [
                PartySchema(
                    name=     p.name,
                    role=     p.role,
                    source=   SourceReferenceSchema(
                        page_number=   p.source.page_number,
                        chunk_id=      p.source.chunk_id,
                        document_id=   p.source.document_id,
                        document_name= p.source.document_name,
                    ),
                    evidence= p.evidence,
                )
                for p in ea.parties
            ],
            key_dates= [
                KeyDateSchema(
                    date=     d.date,
                    type=     d.type,
                    source=   SourceReferenceSchema(
                        page_number=   d.source.page_number,
                        chunk_id=      d.source.chunk_id,
                        document_id=   d.source.document_id,
                        document_name= d.source.document_name,
                    ),
                    evidence= d.evidence,
                )
                for d in ea.key_dates
            ],
            obligations= [
                ObligationSchema(
                    party=      o.party,
                    obligation= o.obligation,
                    deadline=   o.deadline or "Not specified",
                    source=     ClauseSourceSchema(
                        page_number= o.source.page_number,
                        chunk_id=    o.source.chunk_id,
                    ),
                    condition=  o.condition,
                    evidence=   o.evidence,
                )
                for o in ea.obligations
            ],
            provider_used= ea.provider_used,
        )

    # Audit: DOCUMENT_ANALYZED — write before building the heavy response object
    write_audit_event(
        db=db, event_type=AuditEventType.DOCUMENT_ANALYZED,
        user_id=current_user.id, resource_type="document", resource_id=document_id,
        success=result.analysis_successful,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"filename": doc.filename, "provider": result.provider_used},
    )

    return DocumentAnalysisResponse(
        document_id=         result.document_id,
        filename=            result.filename,
        document_type=       result.document_type,
        jurisdiction=        result.jurisdiction,
        structured_summary=  structured_summary_schema,
        structured_clauses=  structured_clauses_schema,
        structured_obligations= structured_obligations_schema,
        structured_risk_assessment= structured_risk_assessment_schema,
        structured_missing_ambiguous= structured_missing_ambiguous_schema,
        structured_entities= structured_entities_schema,
        summary=             result.summary,
        important_clauses=   result.important_clauses,
        risks=               result.risks,
        missing_ambiguous=   result.missing_ambiguous,
        key_dates=           result.key_dates,
        parties=             result.parties,
        obligations=         result.obligations,
        citations=           result.citations,
        provider_used=       result.provider_used,
        analysis_successful= result.analysis_successful,
        error_message=       result.error_message,
    )
    # Audit: DOCUMENT_ANALYZED
    write_audit_event(
        db=db, event_type=AuditEventType.DOCUMENT_ANALYZED,
        user_id=current_user.id, resource_type="document", resource_id=document_id,
        success=result.analysis_successful,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
        metadata={"filename": doc.filename, "provider": result.provider_used},
    )
