from typing import Dict, Any, List
from app.services.security.prompt_injection.rules import (
    DIRECT_INJECTION_PATTERNS,
    INDIRECT_DOCUMENT_INJECTION_PATTERNS,
    check_patterns
)


class InputSecurityScanner:
    """
    Screens direct user queries for prompt injection, jailbreak syntax, and unsafe inputs.
    """

    def scan_query(self, query: str) -> Dict[str, Any]:
        if not query or not query.strip():
            return {
                "is_safe": False,
                "threat_score": 1.0,
                "detected_threats": ["Empty query string"],
                "sanitized_text": ""
            }

        matched_patterns = check_patterns(query, DIRECT_INJECTION_PATTERNS)
        is_safe = len(matched_patterns) == 0
        threat_score = 0.95 if matched_patterns else 0.0

        return {
            "is_safe": is_safe,
            "threat_score": threat_score,
            "detected_threats": matched_patterns,
            "sanitized_text": query.strip()
        }


class DocumentSecurityScanner:
    """
    Screens retrieved document chunks for indirect prompt injection attacks
    embedded inside uploaded third-party or opposing-counsel documents.
    """

    def scan_document_chunk(self, chunk_text: str, document_id: Any = None) -> Dict[str, Any]:
        if not chunk_text:
            return {
                "contains_indirect_injection": False,
                "threat_score": 0.0,
                "detected_threats": [],
                "document_id": document_id
            }

        matched_direct = check_patterns(chunk_text, DIRECT_INJECTION_PATTERNS)
        matched_indirect = check_patterns(chunk_text, INDIRECT_DOCUMENT_INJECTION_PATTERNS)
        all_threats = matched_direct + matched_indirect

        has_injection = len(all_threats) > 0
        threat_score = 0.85 if has_injection else 0.0

        return {
            "contains_indirect_injection": has_injection,
            "threat_score": threat_score,
            "detected_threats": all_threats,
            "document_id": document_id
        }


input_scanner = InputSecurityScanner()
document_scanner = DocumentSecurityScanner()
