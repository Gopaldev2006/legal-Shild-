import re
from typing import Dict, Any
from app.services.security.prompt_injection import input_scanner


class QueryProcessor:
    """
    Query Security Screening & Input Sanitizer Module.
    Screens legal user queries for prompt injection, system override attacks,
    unauthorized cross-tenant extraction attempts, and unsafe content.
    """

    def screen_query(self, query: str) -> Dict[str, Any]:
        """
        Screens input query for security threats and returns safety status.
        """
        scan_res = input_scanner.scan_query(query)

        cleaned_query = (query or "").strip()
        sanitized_query = re.sub(r"[\r\n\t]+", " ", cleaned_query)
        sanitized_query = re.sub(r"\s+", " ", sanitized_query).strip()

        detected_threats = []
        for m in scan_res.get("detected_threats", []):
            p_id = m.get("pattern_id", "UNKNOWN") if isinstance(m, dict) else str(m)
            detected_threats.append(f"Prompt injection pattern detected: '{p_id}'")


        return {
            "is_safe": scan_res["is_safe"],
            "sanitized_query": sanitized_query,
            "risk_score": scan_res["threat_score"],
            "detected_threats": detected_threats,
        }

