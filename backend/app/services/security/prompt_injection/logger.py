"""
Security Audit Logging Module for Prompt Injection Defense.

Tracks, formats, and records security audit events when direct or indirect
prompt injections, jailbreaks, or system prompt leaks are detected.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger("security.prompt_injection")

class SecurityAuditLogger:
    """Logs prompt injection defense audit events."""

    def __init__(self):
        self._audit_history: List[Dict[str, Any]] = []

    def log_injection_event(
        self,
        event_type: str,  # "direct_injection", "indirect_document_injection", "system_prompt_leak"
        source: str,       # "user_query", "retrieved_document", "output_validation"
        severity: str,     # "CRITICAL", "HIGH", "MEDIUM"
        matches: List[Dict[str, Any]],
        user_id: Optional[str] = None,
        document_id: Optional[str] = None,
        context_snippet: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record a security injection event.
        """
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "source": source,
            "severity": severity,
            "user_id": user_id or "anonymous",
            "document_id": document_id,
            "rules_triggered": [m.get("pattern_id", "UNKNOWN") for m in matches],
            "details": matches,
            "snippet_preview": context_snippet[:150] if context_snippet else None,
        }

        self._audit_history.append(event)

        log_msg = (
            f"[SECURITY ALERT] [{severity}] Event: {event_type} | Source: {source} | "
            f"User: {event['user_id']} | Document: {document_id} | "
            f"Rules Triggered: {event['rules_triggered']}"
        )
        if severity == "CRITICAL":
            logger.critical(log_msg)
        elif severity == "HIGH":
            logger.error(log_msg)
        else:
            logger.warning(log_msg)

        return event

    def get_audit_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recorded security audit events."""
        return self._audit_history[-limit:]

# Singleton instance
audit_logger = SecurityAuditLogger()
