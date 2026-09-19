"""
Sensitive Data Detection & PII Masking Module.

Identifies and redacts Personally Identifiable Information (PII) and confidential
tokens (Indian PAN, Aadhaar, SSN, Credit Cards, API Keys, Phone Numbers) from text.
"""

import re
from typing import Dict, Any, List


class SensitiveDataDetector:
    """
    Scans and redacts PII and confidential internal signatures.
    """

    PATTERNS = {
        "INDIAN_PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
        "INDIAN_AADHAAR": r"\b[2-9]{1}[0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b",
        "US_SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "API_KEY_TOKEN": r"\b(?:sk|pk|api|key)_[a-zA-Z0-9_]{16,}\b",
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    }


    def detect_sensitive_data(self, text: str) -> List[Dict[str, Any]]:
        """
        Detects sensitive PII patterns in text.
        """
        if not text:
            return []

        detected = []
        for p_name, regex in self.PATTERNS.items():
            matches = re.findall(regex, text)
            if matches:
                for match in set(matches):
                    detected.append({
                        "pii_type": p_name,
                        "matched_text": match,
                    })

        return detected

    def sanitize_text(self, text: str) -> Dict[str, Any]:
        """
        Redacts all identified PII tokens with standard privacy redaction tags.
        """
        if not text:
            return {"sanitized_text": "", "redactions_applied": []}

        sanitized = text
        redactions = []

        for p_name, regex in self.PATTERNS.items():
            matches = re.findall(regex, sanitized)
            if matches:
                for m in set(matches):
                    replacement = f"[REDACTED_{p_name}]"
                    sanitized = sanitized.replace(m, replacement)
                    redactions.append({"pii_type": p_name, "original": m, "redacted_with": replacement})

        return {
            "sanitized_text": sanitized,
            "redactions_applied": redactions,
        }


sensitive_data_detector = SensitiveDataDetector()
