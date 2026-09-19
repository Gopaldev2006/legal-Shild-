import re


def clean_case_text(text: str) -> str:
    """
    Sanitizes legal case text by stripping control chars, headers, and extra whitespace.
    """
    if not text:
        return "Not available in the indexed source."

    cleaned = text.strip()
    cleaned = re.sub(r"[\r\n\t]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned if cleaned else "Not available in the indexed source."
