"""
analytics_service.py — Admin Analytics Calculations
=====================================================
Provides all analytics data for the Admin Analytics Dashboard.

Design principles:
  - Uses SQL COUNT/GROUP BY aggregations — never loads full rows into Python
  - Never exposes passwords, tokens, keys, or legal document content
  - Every public function handles its own exceptions and returns safe defaults
    so analytics failures never crash the main application
  - All data sourced from EXISTING tables — no schema changes required

Data sources:
  users             → user counts by role / new users over time
  legal_documents   → document counts by status and type
  chat_messages     → AI usage (model_used field: "gemini" | "free-legal-engine")
  rag_audit_logs    → RAG-specific query counts (legacy compliance table)
  conversations     → conversation counts by mode
  audit_logs        → recent activity feed (25 event types)
  user_sessions     → active session count
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.document import LegalDocument, ProcessingStatus
from app.models.conversation import Conversation, ChatMessage, ConversationMode, MessageRole
from app.models.audit import RAGAuditLog
from app.models.audit_log import AuditLog, AuditEventType
from app.models.session import UserSession

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_count(fn, fallback: int = 0) -> int:
    """Run a count function; return fallback on any exception."""
    try:
        result = fn()
        return result if result is not None else fallback
    except Exception as exc:
        logger.warning("Analytics count failed: %s", type(exc).__name__)
        return fallback


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# User analytics
# ─────────────────────────────────────────────────────────────────────────────

def _user_stats(db: Session) -> Dict[str, Any]:
    """
    Counts users by role using a single GROUP BY query.
    Also counts new registrations in the last 7 and 30 days.
    """
    try:
        # Single aggregation query — count by role
        rows = (
            db.query(User.role, func.count(User.id).label("cnt"))
            .group_by(User.role)
            .all()
        )
        role_map = {r.role.value: r.cnt for r in rows}

        total    = sum(role_map.values())
        public   = role_map.get(UserRole.PUBLIC_USER.value, 0)
        pro      = role_map.get(UserRole.LEGAL_PROFESSIONAL.value, 0)
        admin    = role_map.get(UserRole.ADMIN.value, 0)

        now = _now_utc()
        new_7d  = db.query(func.count(User.id)).filter(
            User.created_at >= now - timedelta(days=7)
        ).scalar() or 0
        new_30d = db.query(func.count(User.id)).filter(
            User.created_at >= now - timedelta(days=30)
        ).scalar() or 0

        return {
            "total":         total,
            "public":        public,
            "professionals": pro,
            "admins":        admin,
            "new_last_7_days":  new_7d,
            "new_last_30_days": new_30d,
        }
    except Exception as exc:
        logger.warning("User stats failed: %s", type(exc).__name__)
        return {
            "total": 0, "public": 0, "professionals": 0, "admins": 0,
            "new_last_7_days": 0, "new_last_30_days": 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Document analytics
# ─────────────────────────────────────────────────────────────────────────────

def _document_stats(db: Session) -> Dict[str, Any]:
    """
    Counts documents by status and type using GROUP BY.
    No soft-delete exists — every row in the table is a real document.
    """
    try:
        total = db.query(func.count(LegalDocument.id)).scalar() or 0

        # Group by processing_status
        status_rows = (
            db.query(LegalDocument.processing_status, func.count(LegalDocument.id).label("cnt"))
            .group_by(LegalDocument.processing_status)
            .all()
        )
        by_status = {r.processing_status.value: r.cnt for r in status_rows}

        # Group by document_type
        type_rows = (
            db.query(LegalDocument.document_type, func.count(LegalDocument.id).label("cnt"))
            .group_by(LegalDocument.document_type)
            .all()
        )
        by_type = {r.document_type.value: r.cnt for r in type_rows}

        # Ready/completed (usable) vs failed
        ready = (
            by_status.get(ProcessingStatus.READY.value, 0) +
            by_status.get(ProcessingStatus.COMPLETED.value, 0)
        )
        failed = by_status.get(ProcessingStatus.FAILED.value, 0)

        return {
            "total":      total,
            "ready":      ready,
            "failed":     failed,
            "by_status":  by_status,
            "by_type":    by_type,
        }
    except Exception as exc:
        logger.warning("Document stats failed: %s", type(exc).__name__)
        return {"total": 0, "ready": 0, "failed": 0, "by_status": {}, "by_type": {}}


# ─────────────────────────────────────────────────────────────────────────────
# AI / chat analytics
# ─────────────────────────────────────────────────────────────────────────────

def _ai_stats(db: Session) -> Dict[str, Any]:
    """
    AI usage analytics derived from two sources:

    1. chat_messages.model_used — normalised strings stored by _dispatch_ai():
         "gemini"            → successful Gemini response
         "free-legal-engine" → Free AI Legal Engine response
         "error-fallback"    → AI dispatch error (very rare)

    2. rag_audit_logs — RAG query compliance log (legacy, records all Tier 2 RAG calls)

    We count chat_messages WHERE role='assistant' for AI totals.
    Gemini/fallback breakdown from model_used.
    """
    try:
        # Total assistant messages (= total AI responses across all conversations)
        total_chat_ai = (
            db.query(func.count(ChatMessage.id))
            .filter(ChatMessage.role == MessageRole.ASSISTANT)
            .scalar() or 0
        )

        # Gemini count
        gemini_count = (
            db.query(func.count(ChatMessage.id))
            .filter(
                ChatMessage.role       == MessageRole.ASSISTANT,
                ChatMessage.model_used == "gemini",
            )
            .scalar() or 0
        )

        # Fallback count
        fallback_count = (
            db.query(func.count(ChatMessage.id))
            .filter(
                ChatMessage.role       == MessageRole.ASSISTANT,
                ChatMessage.model_used == "free-legal-engine",
            )
            .scalar() or 0
        )

        # RAG-specific queries from compliance table
        total_rag = db.query(func.count(RAGAuditLog.id)).scalar() or 0

        # Gemini percentage (avoid ZeroDivisionError)
        gemini_pct = (
            round(gemini_count / total_chat_ai * 100, 1)
            if total_chat_ai > 0 else 0.0
        )

        # Conversation counts by mode
        conv_rows = (
            db.query(Conversation.mode, func.count(Conversation.id).label("cnt"))
            .group_by(Conversation.mode)
            .all()
        )
        by_mode = {r.mode.value: r.cnt for r in conv_rows}
        total_conversations = sum(by_mode.values())

        return {
            "total_ai_responses":   total_chat_ai,
            "total_rag_queries":    total_rag,
            "gemini_queries":       gemini_count,
            "fallback_queries":     fallback_count,
            "gemini_percentage":    gemini_pct,
            "total_conversations":  total_conversations,
            "conversations_by_mode": by_mode,
        }
    except Exception as exc:
        logger.warning("AI stats failed: %s", type(exc).__name__)
        return {
            "total_ai_responses": 0, "total_rag_queries": 0,
            "gemini_queries": 0, "fallback_queries": 0,
            "gemini_percentage": 0.0, "total_conversations": 0,
            "conversations_by_mode": {},
        }


# ─────────────────────────────────────────────────────────────────────────────
# Session analytics
# ─────────────────────────────────────────────────────────────────────────────

def _session_stats(db: Session) -> Dict[str, Any]:
    """Counts active (non-revoked, non-expired) sessions."""
    try:
        now = _now_utc()
        active = (
            db.query(func.count(UserSession.id))
            .filter(
                UserSession.revoked_at == None,   # noqa: E711
                UserSession.expires_at > now,
            )
            .scalar() or 0
        )
        return {"active_sessions": active}
    except Exception as exc:
        logger.warning("Session stats failed: %s", type(exc).__name__)
        return {"active_sessions": 0}


# ─────────────────────────────────────────────────────────────────────────────
# Recent activity
# ─────────────────────────────────────────────────────────────────────────────

def get_recent_activity(db: Session, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Returns the most recent audit log entries as a safe activity feed.

    Fields returned:
      id, event_type, user_id, resource_type, resource_id, success, created_at

    Intentionally excluded (never in audit_logs anyway due to _sanitise_metadata):
      passwords, tokens, API keys, legal document content
    """
    try:
        logs = (
            db.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

        # Resolve user emails in a single pass (best-effort)
        user_ids = list({log.user_id for log in logs if log.user_id is not None})
        users = db.query(User.id, User.email).filter(User.id.in_(user_ids)).all()
        email_map = {u.id: u.email for u in users}

        return [
            {
                "id":            log.id,
                "event_type":    log.event_type.value,
                "user_id":       log.user_id,
                "user_email":    email_map.get(log.user_id) if log.user_id else None,
                "resource_type": log.resource_type,
                "resource_id":   log.resource_id,
                "success":       log.success,
                "created_at":    log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    except Exception as exc:
        logger.warning("Recent activity failed: %s", type(exc).__name__)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_analytics_summary(db: Session) -> Dict[str, Any]:
    """
    Returns the full analytics summary dict.

    All sub-functions handle their own exceptions so a single failure
    does not break the entire response.
    """
    return {
        "users":     _user_stats(db),
        "documents": _document_stats(db),
        "ai":        _ai_stats(db),
        "sessions":  _session_stats(db),
        "generated_at": _now_utc().isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Time-series analytics (Phase 4)
# ─────────────────────────────────────────────────────────────────────────────

def get_timeseries(db: Session, days: int) -> List[Dict[str, Any]]:
    """
    Returns per-day aggregated analytics for the last `days` calendar days
    (including today).

    Supported values for `days`: 1 (today only), 7, 30.
    Any other positive integer is also accepted.

    Each element in the returned list:
      {
        "date":      "YYYY-MM-DD",   ← UTC date string
        "users":     int,            ← new user registrations that day
        "documents": int,            ← documents uploaded that day
        "ai_total":  int,            ← total AI assistant messages that day
        "gemini":    int,            ← Gemini-powered AI messages that day
        "fallback":  int,            ← fallback AI messages that day
      }

    Days with zero activity are included so the frontend always has a
    complete date range (no gaps to fill client-side).

    All queries use SQL date-level filtering — no full-table Python iteration.
    Exceptions are caught; the affected day returns zero values.
    """
    now   = _now_utc()
    # Start of today UTC (midnight)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Earliest day to include
    start = today_start - timedelta(days=days - 1)

    # Build the list of calendar dates (oldest first)
    date_range = [
        (start + timedelta(days=i)).date()
        for i in range(days)
    ]

    # ── Aggregate all metrics in bulk — one query per metric ─────────────────

    def _date_counts(column_date):
        """
        Returns a dict {date_obj: count} for rows where column_date falls
        within [start, now].  Uses SQLite strftime for date extraction.
        """
        from sqlalchemy import text
        return {}   # placeholder — implemented per-model below

    # Helper: strip to date string (SQLite stores DateTime as ISO strings)
    def _iso_to_date(iso_str: str) -> str:
        """'2026-09-10T14:32:00+00:00' → '2026-09-10'"""
        return iso_str[:10] if iso_str else ""

    # ── Users: created_at in range ────────────────────────────────────────────
    try:
        user_rows = (
            db.query(User.created_at)
            .filter(User.created_at >= start)
            .all()
        )
        user_by_date: Dict[str, int] = {}
        for (dt,) in user_rows:
            key = dt.strftime("%Y-%m-%d") if dt else None
            if key:
                user_by_date[key] = user_by_date.get(key, 0) + 1
    except Exception as exc:
        logger.warning("Timeseries user query failed: %s", type(exc).__name__)
        user_by_date = {}

    # ── Documents: created_at in range ───────────────────────────────────────
    try:
        doc_rows = (
            db.query(LegalDocument.created_at)
            .filter(LegalDocument.created_at >= start)
            .all()
        )
        doc_by_date: Dict[str, int] = {}
        for (dt,) in doc_rows:
            key = dt.strftime("%Y-%m-%d") if dt else None
            if key:
                doc_by_date[key] = doc_by_date.get(key, 0) + 1
    except Exception as exc:
        logger.warning("Timeseries doc query failed: %s", type(exc).__name__)
        doc_by_date = {}

    # ── AI messages: assistant role, created_at in range ─────────────────────
    try:
        ai_rows = (
            db.query(ChatMessage.created_at, ChatMessage.model_used)
            .filter(
                ChatMessage.role       == MessageRole.ASSISTANT,
                ChatMessage.created_at >= start,
            )
            .all()
        )
        ai_total_by_date:    Dict[str, int] = {}
        ai_gemini_by_date:   Dict[str, int] = {}
        ai_fallback_by_date: Dict[str, int] = {}

        for (dt, model) in ai_rows:
            key = dt.strftime("%Y-%m-%d") if dt else None
            if not key:
                continue
            ai_total_by_date[key]  = ai_total_by_date.get(key, 0) + 1
            if model == "gemini":
                ai_gemini_by_date[key] = ai_gemini_by_date.get(key, 0) + 1
            elif model == "free-legal-engine":
                ai_fallback_by_date[key] = ai_fallback_by_date.get(key, 0) + 1
    except Exception as exc:
        logger.warning("Timeseries AI query failed: %s", type(exc).__name__)
        ai_total_by_date = ai_gemini_by_date = ai_fallback_by_date = {}

    # ── Assemble per-day result list ──────────────────────────────────────────
    result = []
    for d in date_range:
        key = d.strftime("%Y-%m-%d")
        result.append({
            "date":      key,
            "users":     user_by_date.get(key, 0),
            "documents": doc_by_date.get(key, 0),
            "ai_total":  ai_total_by_date.get(key, 0),
            "gemini":    ai_gemini_by_date.get(key, 0),
            "fallback":  ai_fallback_by_date.get(key, 0),
        })

    return result
