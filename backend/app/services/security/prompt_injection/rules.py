import re
from typing import List, Dict, Any

# Threat Category Patterns
DIRECT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above)\s+instructions",
    r"system\s*:\s*",
    r"override\s+security",
    r"reveal\s+(all|other)\s+documents",
    r"act\s+as\s+admin",
    r"show\s+system\s+prompt",
    r"bypass\s+permission",
    r"drop\s+table",
    r"select\s+\*\s+from",
    r"<script>",
    r"eval\(",
]

INDIRECT_DOCUMENT_INJECTION_PATTERNS = [
    r"ignore\s+the\s+user's\s+question",
    r"disclose\s+system\s+prompt",
    r"print\s+the\s+system\s+instructions",
    r"system\s+override",
    r"unauthorized\s+data\s+dump",
    r"forget\s+all\s+rules",
    r"pretend\s+you\s+are\s+root",
]

SYSTEM_PROMPT_LEAK_PATTERNS = [
    r"SECURITY POLICY & SYSTEM GUARDRAILS",
    r"AUTHORIZED CONTEXT CHUNKS",
    r"USER QUERY:",
    r"LEGAL ANALYSIS:",
]


def check_patterns(text: str, patterns: List[str]) -> List[str]:
    """
    Returns list of matched injection pattern strings.
    """
    if not text:
        return []

    matches = []
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            matches.append(pattern)
    return matches
