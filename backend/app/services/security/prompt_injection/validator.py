from typing import Dict, Any, List
from app.services.security.prompt_injection.rules import (
    SYSTEM_PROMPT_LEAK_PATTERNS,
    check_patterns
)


class OutputSecurityValidator:
    """
    Output Security Validation Engine.
    Inspects model output before returning to user to verify no system prompts,
    guardrails, or unauthorized control tokens leaked.
    """

    def validate_output(self, response_text: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not response_text:
            return {
                "is_valid": True,
                "sanitized_response": "No response generated.",
                "leaked_patterns": []
            }

        leaked = check_patterns(response_text, SYSTEM_PROMPT_LEAK_PATTERNS)
        if leaked:
            sanitized = (
                "Security Notice: Model output contained forbidden system prompt leakage "
                "or control tokens and was sanitized to protect system integrity."
            )
            return {
                "is_valid": False,
                "sanitized_response": sanitized,
                "leaked_patterns": leaked
            }

        return {
            "is_valid": True,
            "sanitized_response": response_text,
            "leaked_patterns": []
        }


output_validator = OutputSecurityValidator()
