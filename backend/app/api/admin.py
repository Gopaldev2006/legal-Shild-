"""
Admin Management & System Monitoring API Router.

Provides admin-only management endpoints for dashboard metrics, user administration,
verification reviews, document audits, security event logs, and SLM model status.
All endpoints strictly require ADMIN role authorization.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.api.deps import get_db, require_roles
from app.models.user import User, UserRole, VerificationStatus
from app.models.verification import VerificationRequest
from app.models.document import LegalDocument, DocumentChunk
from app.models.audit import RAGAuditLog
from app.schemas.verification import AdminReviewAction
from app.core.config import settings
from app.services.security.prompt_injection.logger import audit_logger as prompt_injection_logger
from app.services.security.privacy.logger import privacy_audit_logger
from app.services.system.benchmark_engine import benchmark_engine
from app.services.audit.audit_service import write_audit_event
from app.models.audit_log import AuditLog, AuditEventType
from app.services.analytics.analytics_service import get_analytics_summary, get_recent_activity, get_timeseries

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard-summary", summary="Admin Overview Summary Cards")
def get_dashboard_summary(
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns summary counts for admin dashboard metrics cards.
    Restricted strictly to ADMIN role.
    """
    total_users = db.query(User).count()
    verified_professionals = db.query(User).filter(User.role == UserRole.LEGAL_PROFESSIONAL).count()
    pending_verifications = db.query(VerificationRequest).filter(VerificationRequest.status == VerificationStatus.PENDING).count()
    total_documents = db.query(LegalDocument).count()
    total_rag_queries = db.query(RAGAuditLog).count()

    prompt_events = prompt_injection_logger.get_audit_history()
    privacy_events = privacy_audit_logger.get_audit_history()
    total_security_events = len(prompt_events) + len(privacy_events)

    memory_mb = benchmark_engine.get_memory_usage_mb()

    return {
        "cards": {
            "total_users": total_users,
            "verified_professionals": verified_professionals,
            "pending_verifications": pending_verifications,
            "total_documents": total_documents,
            "total_rag_queries": total_rag_queries,
            "total_security_events": total_security_events,
        },
        "system_health": {
            "memory_usage_mb": memory_mb,
            "status": "HEALTHY" if memory_mb < 2048.0 else "WARNING",
        },
        "model_status": {
            "model_name": settings.MODEL_NAME,
            "use_finetuned_model": settings.USE_FINETUNED_MODEL,
            "device": settings.DEVICE,
        }
    }


@router.get("/users", summary="Admin User Management Table")
def list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    verification_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns paginated user list with search and role/status filtering.
    Restricted strictly to ADMIN role.
    """
    query_obj = db.query(User)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query_obj = query_obj.filter(or_(User.name.ilike(term), User.email.ilike(term)))

    if role and role.strip():
        query_obj = query_obj.filter(User.role == role.strip())

    if verification_status and verification_status.strip():
        query_obj = query_obj.filter(User.verification_status == verification_status.strip())

    total_count = query_obj.count()
    offset = (page - 1) * limit
    users = query_obj.order_by(User.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for u in users:
        v_req = db.query(VerificationRequest).filter(VerificationRequest.user_id == u.id).order_by(VerificationRequest.created_at.desc()).first()
        items.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role.value,
            "verification_status": u.verification_status.value,
            "bar_card_number": v_req.extracted_text[:30] if v_req and v_req.extracted_text else "N/A",
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })


    return {
        "items": items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if total_count > 0 else 1,
    }


@router.get("/verifications", summary="Admin List Verification Requests")
def list_verifications(
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Returns list of all professional verification requests for Admin review.
    Restricted strictly to ADMIN role.
    """
    requests = (
        db.query(VerificationRequest)
        .order_by(VerificationRequest.created_at.desc())
        .all()
    )

    results = []
    for req in requests:
        applicant = db.query(User).filter(User.id == req.user_id).first()
        results.append({
            "id": req.id,
            "user_id": req.user_id,
            "applicant_name": applicant.name if applicant else "Unknown",
            "applicant_email": applicant.email if applicant else "Unknown",
            "bar_card_number": applicant.bar_card_number if applicant else None,
            "document_hash": req.document_hash,
            "extracted_text": req.extracted_text,
            "status": req.status.value,
            "reviewer_id": req.reviewer_id,
            "review_notes": req.review_notes,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None
        })

    return results


@router.post("/verifications/{verification_id}/approve", summary="Admin Approve Verification")
def approve_verification(
    verification_id: int,
    action_in: Optional[AdminReviewAction] = None,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Approves a professional verification request.
    Elevates applicant user role to LEGAL_PROFESSIONAL and status to VERIFIED.
    Restricted strictly to ADMIN role.
    """
    req = db.query(VerificationRequest).filter(VerificationRequest.id == verification_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification request not found")

    applicant = db.query(User).filter(User.id == req.user_id).first()
    if not applicant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant user record not found")

    req.status = VerificationStatus.VERIFIED
    req.reviewer_id = current_admin.id
    req.review_notes = action_in.review_notes if action_in else "Approved by Admin"
    req.reviewed_at = datetime.now(timezone.utc)

    applicant.role = UserRole.LEGAL_PROFESSIONAL
    applicant.verification_status = VerificationStatus.VERIFIED

    db.add(req)
    db.add(applicant)
    db.commit()
    db.refresh(req)
    db.refresh(applicant)

    # Audit: VERIFICATION_APPROVED
    write_audit_event(
        db=db, event_type=AuditEventType.VERIFICATION_APPROVED,
        user_id=current_admin.id, resource_type="verification", resource_id=req.id,
        success=True, metadata={"applicant_id": applicant.id, "applicant_email": applicant.email},
    )

    return {
        "message": f"Verification approved successfully for {applicant.email}",
        "user_id": applicant.id,
        "new_role": applicant.role.value,
        "verification_status": applicant.verification_status.value,
        "verification_id": req.id
    }


@router.post("/verifications/{verification_id}/reject", summary="Admin Reject Verification")
def reject_verification(
    verification_id: int,
    action_in: Optional[AdminReviewAction] = None,
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """
    Rejects a professional verification request.
    Sets applicant verification_status to REJECTED. Role remains PUBLIC_USER.
    Restricted strictly to ADMIN role.
    """
    req = db.query(VerificationRequest).filter(VerificationRequest.id == verification_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification request not found")

    applicant = db.query(User).filter(User.id == req.user_id).first()
    if not applicant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Applicant user record not found")

    req.status = VerificationStatus.REJECTED
    req.reviewer_id = current_admin.id
    req.review_notes = action_in.review_notes if action_in else "Rejected by Admin"
    req.reviewed_at = datetime.now(timezone.utc)

    applicant.verification_status = VerificationStatus.REJECTED

    db.add(req)
    db.add(applicant)
    db.commit()
    db.refresh(req)
    db.refresh(applicant)

    # Audit: VERIFICATION_REJECTED
    write_audit_event(
        db=db, event_type=AuditEventType.VERIFICATION_REJECTED,
        user_id=current_admin.id, resource_type="verification", resource_id=req.id,
        success=True, metadata={"applicant_id": applicant.id},
    )

    return {
        "message": f"Verification rejected for {applicant.email}",
        "user_id": applicant.id,
        "role": applicant.role.value,
        "verification_status": applicant.verification_status.value,
        "verification_id": req.id
    }


@router.get("/documents", summary="Admin System-Wide Document Audit")
def list_system_documents(
    search: Optional[str] = None,
    processing_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns paginated system-wide document list with owner emails and chunk counts.
    Restricted strictly to ADMIN role.
    """
    query_obj = db.query(LegalDocument)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query_obj = query_obj.filter(LegalDocument.filename.ilike(term))

    if processing_status and processing_status.strip():
        query_obj = query_obj.filter(LegalDocument.processing_status == processing_status.strip())

    total_count = query_obj.count()
    offset = (page - 1) * limit
    docs = query_obj.order_by(LegalDocument.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for doc in docs:
        owner = db.query(User).filter(User.id == doc.owner_id).first()
        chunk_count = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).count()
        items.append({
            "id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "document_type": doc.document_type.value,
            "processing_status": doc.processing_status.value,
            "owner_id": doc.owner_id,
            "owner_name": owner.name if owner else "Unknown",
            "owner_email": owner.email if owner else "Unknown",
            "chunk_count": chunk_count,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
        })

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if total_count > 0 else 1,
    }


@router.get("/security-events", summary="Admin Security Threat Events Audit")
def get_security_events(
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Returns aggregated security events from prompt injection and data leakage protection loggers.
    Restricted strictly to ADMIN role.
    """
    prompt_events = prompt_injection_logger.get_audit_history()
    privacy_events = privacy_audit_logger.get_audit_history()

    all_events = prompt_events + privacy_events
    all_events.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    if event_type and event_type.strip():
        all_events = [e for e in all_events if e.get("event_type") == event_type.strip()]

    if severity and severity.strip():
        all_events = [e for e in all_events if e.get("severity") == severity.strip()]

    total_count = len(all_events)
    offset = (page - 1) * limit
    paginated_events = all_events[offset: offset + limit]

    return {
        "items": paginated_events,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": (total_count + limit - 1) // limit if total_count > 0 else 1,
    }


@router.get("/model-status", summary="Admin SLM & AI Engine Configuration Status")
def get_model_status(
    current_admin: User = Depends(require_roles(UserRole.ADMIN))
) -> Dict[str, Any]:
    """
    Returns detailed AI model configuration, fine-tuning status, and hardware parameters.
    Restricted strictly to ADMIN role.
    """
    return {
        "base_model": settings.MODEL_NAME,
        "use_finetuned_model": settings.USE_FINETUNED_MODEL,
        "adapter_path": settings.ADAPTER_PATH,
        "max_new_tokens": settings.MAX_NEW_TOKENS,
        "temperature": settings.TEMPERATURE,
        "device": settings.DEVICE,
        "status": "OPERATIONAL",
    }


@router.get("/audit-logs", summary="Admin Security Audit Log Viewer")
def get_audit_logs(
    event_type:    Optional[str] = None,
    user_id:       Optional[int] = None,
    resource_type: Optional[str] = None,
    success:       Optional[bool] = None,
    date_from:     Optional[str] = None,   # ISO date string YYYY-MM-DD
    date_to:       Optional[str] = None,   # ISO date string YYYY-MM-DD
    page:          int           = Query(1,  ge=1),
    limit:         int           = Query(20, ge=1, le=100),
    current_admin: User          = Depends(require_roles(UserRole.ADMIN)),
    db:            Session       = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns paginated security audit log records.

    Filters:
      - event_type    : e.g. LOGIN_SUCCESS, DOCUMENT_UPLOADED
      - user_id       : filter by specific user
      - resource_type : "document" | "chat" | "session" | "user" | "api_key"
      - success       : true = successful events; false = failures/denials
      - date_from     : ISO date lower bound (inclusive)
      - date_to       : ISO date upper bound (inclusive)

    Security: ADMIN only.  Sensitive fields (metadata_json) are returned as-is
    because admin is trusted, but are guaranteed never to contain secrets
    (enforced at write time by audit_service._sanitise_metadata).
    """
    from app.models.audit_log import AuditLog, AuditEventType
    from datetime import datetime, timezone
    from sqlalchemy import desc

    q = db.query(AuditLog)

    if event_type:
        try:
            q = q.filter(AuditLog.event_type == AuditEventType(event_type.strip()))
        except ValueError:
            pass  # unknown event type — ignore filter silently

    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)

    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type.strip())

    if success is not None:
        q = q.filter(AuditLog.success == success)

    if date_from:
        try:
            dt = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            q  = q.filter(AuditLog.created_at >= dt)
        except ValueError:
            pass

    if date_to:
        try:
            from datetime import timedelta
            dt = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
            q  = q.filter(AuditLog.created_at < dt)
        except ValueError:
            pass

    total = q.count()
    logs  = (
        q.order_by(desc(AuditLog.created_at))
         .offset((page - 1) * limit)
         .limit(limit)
         .all()
    )

    # Resolve user email for display (best-effort — no error if user deleted)
    user_cache: Dict[int, str] = {}

    def _email(uid: Optional[int]) -> Optional[str]:
        if uid is None:
            return None
        if uid not in user_cache:
            u = db.query(User).filter(User.id == uid).first()
            user_cache[uid] = u.email if u else f"user#{uid}"
        return user_cache[uid]

    items = [
        {
            "id":            log.id,
            "event_type":    log.event_type.value,
            "user_id":       log.user_id,
            "user_email":    _email(log.user_id),
            "resource_type": log.resource_type,
            "resource_id":   log.resource_id,
            "success":       log.success,
            "ip_address":    log.ip_address,
            "metadata":      log.metadata_json,
            "created_at":    log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]

    return {
        "items":       items,
        "total":       total,
        "page":        page,
        "limit":       limit,
        "total_pages": (total + limit - 1) // limit if total > 0 else 1,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Analytics Endpoints (Phase: Admin Analytics)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/analytics/summary", summary="Admin Analytics Summary")
def get_analytics_summary_endpoint(
    current_admin: User    = Depends(require_roles(UserRole.ADMIN)),
    db:            Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns aggregated analytics across users, documents, AI usage, and sessions.

    Data sources:
      users             → counts by role, new registrations over time
      legal_documents   → counts by processing status and document type
      chat_messages     → AI response counts; Gemini vs fallback breakdown
                          (model_used field: "gemini" | "free-legal-engine")
      rag_audit_logs    → RAG-specific query count (compliance table)
      conversations     → counts by mode (general / document / rag)
      user_sessions     → active session count

    All calculations use SQL COUNT/GROUP BY — no full-table Python iteration.
    Restricted strictly to ADMIN role.
    """
    try:
        return get_analytics_summary(db)
    except Exception as exc:
        logger.error("Analytics summary error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Analytics data could not be retrieved. Please try again.",
        )


@router.get("/analytics/recent-activity", summary="Admin Recent Activity Feed")
def get_recent_activity_endpoint(
    limit:         int  = Query(20, ge=1, le=100),
    current_admin: User    = Depends(require_roles(UserRole.ADMIN)),
    db:            Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns the most recent security and activity events from the audit log.

    Fields returned per event:
      id, event_type, user_id, user_email, resource_type, resource_id,
      success, created_at

    Fields intentionally excluded:
      passwords, tokens, API keys, legal document content, IP addresses

    Restricted strictly to ADMIN role.
    """
    try:
        items = get_recent_activity(db, limit=limit)
        return {"items": items, "total": len(items)}
    except Exception as exc:
        logger.error("Recent activity error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recent activity could not be retrieved. Please try again.",
        )


@router.get("/analytics/timeseries", summary="Admin Time-Series Analytics")
def get_analytics_timeseries(
    days:          int  = Query(7, ge=1, le=30, description="Number of days: 1 (today), 7, or 30"),
    current_admin: User    = Depends(require_roles(UserRole.ADMIN)),
    db:            Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Returns per-day aggregated analytics for the requested period.

    Supported day values: 1 (today only), 7 (last 7 days), 30 (last 30 days).
    Any value 1–30 is accepted.

    Each element in `data`:
      date      : "YYYY-MM-DD" (UTC)
      users     : new registrations that day
      documents : documents uploaded that day
      ai_total  : total AI assistant messages that day
      gemini    : Gemini-powered messages that day
      fallback  : fallback-engine messages that day

    Days with zero activity are included (no gaps).
    Restricted strictly to ADMIN role.
    """
    try:
        data = get_timeseries(db, days=days)
        return {
            "days":         days,
            "data":         data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("Timeseries analytics error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Time-series analytics could not be retrieved. Please try again.",
        )
