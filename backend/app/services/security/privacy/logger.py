"""
Privacy Audit Logging Module for Data-Leakage Protection.

Tracks and records access refusals, matter boundary violations, and PII redactions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("security.privacy")


class PrivacyAuditLogger:
    """
    Logs privacy and access control audit events.
    """

    def __init__(self):
        self._audit_events: List[Dict[str, Any]] = []

    def log_privacy_event(
        self,
        event_type: str,  # "matter_access_refusal", "unauthorized_chunk_purged", "pii_redaction"
        severity: str,    # "HIGH", "MEDIUM", "INFO"
        user_id: int,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Record a privacy security audit event.
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "severity": severity,
            "user_id": user_id,
            "details": details,
        }

        self._audit_events.append(event)

        log_msg = (
            f"[PRIVACY AUDIT] [{severity}] Event: {event_type} | User: #{user_id} | "
            f"Details: {details}"
        )
        if severity == "HIGH":
            logger.error(log_msg)
        else:
            logger.info(log_msg)

        return event

    def get_audit_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recorded privacy audit events."""
        return self._audit_events[-limit:]


privacy_audit_logger = PrivacyAuditLogger()
