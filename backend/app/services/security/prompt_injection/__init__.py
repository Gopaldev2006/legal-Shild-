"""
Prompt Injection Defense Module Package.

Provides multi-layer security scanning, context isolation, prompt hardening,
and output validation to protect legal RAG pipeline against direct and indirect injections.
"""

from app.services.security.prompt_injection.detector import (
    InputSecurityScanner,
    DocumentSecurityScanner,
    input_scanner,
    document_scanner,
)
from app.services.security.prompt_injection.sanitizer import (
    ContextSanitizer,
    context_sanitizer,
)
from app.services.security.prompt_injection.validator import (
    OutputSecurityValidator,
    output_validator,
)
from app.services.security.prompt_injection.logger import (
    SecurityAuditLogger,
    audit_logger,
)

__all__ = [
    "InputSecurityScanner",
    "DocumentSecurityScanner",
    "input_scanner",
    "document_scanner",
    "ContextSanitizer",
    "context_sanitizer",
    "OutputSecurityValidator",
    "output_validator",
    "SecurityAuditLogger",
    "audit_logger",
]
