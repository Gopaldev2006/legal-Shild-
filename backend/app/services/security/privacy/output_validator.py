"""
Privacy Output Validation Module.

Acts as a post-generation secondary defense filter. Inspects AI response text
to verify no residual unmasked PII or internal cross-tenant metadata leaked.
"""

from typing import Dict, Any, List
from app.services.security.privacy.sensitive_data_detector import sensitive_data_detector


class PrivacyOutputValidator:
    """
    Post-generation secondary safety filter.
    """

    def validate_output_privacy(
        self, response_text: str, current_user_id: int
    ) -> Dict[str, Any]:
        """
        Inspects generated response text for residual PII or unauthorized disclosures.
        """
        if not response_text:
            return {
                "is_clean": True,
                "sanitized_response": "",
                "redactions": [],
            }

        # 1. PII detection & redaction
        pii_res = sensitive_data_detector.sanitize_text(response_text)
        cleaned_text = pii_res["sanitized_text"]
        redactions = pii_res["redactions_applied"]

        # 2. Check for unauthorized cross-tenant owner_id metadata leakage in text
        # e.g., "Owner ID: 999" where 999 != current_user_id
        import re
        cross_tenant_matches = re.findall(r"Owner ID:\s*(\d+)", cleaned_text, re.IGNORECASE)
        for owner_str in cross_tenant_matches:
            if int(owner_str) != current_user_id:
                cleaned_text = re.sub(
                    rf"Owner ID:\s*{owner_str}",
                    "[REDACTED_CROSS_TENANT_OWNER_ID]",
                    cleaned_text
                )
                redactions.append({
                    "pii_type": "CROSS_TENANT_METADATA",
                    "original": f"Owner ID: {owner_str}",
                    "redacted_with": "[REDACTED_CROSS_TENANT_OWNER_ID]"
                })

        is_clean = len(redactions) == 0

        return {
            "is_clean": is_clean,
            "sanitized_response": cleaned_text,
            "redactions": redactions,
        }


privacy_output_validator = PrivacyOutputValidator()
