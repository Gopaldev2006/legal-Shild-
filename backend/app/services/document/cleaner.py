import re


def clean_legal_text(raw_text: str) -> str:
    """
    Cleans and normalizes extracted legal text:
    - Removes non-printable control characters
    - Normalizes irregular whitespace and paragraph spacing
    - Preserves sentence structure and legal citations
    """
    if not raw_text:
        return ""

    # 1. Remove non-printable control characters (except newline, tab)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw_text)

    # 2. Normalize horizontal whitespace
    text = re.sub(r'[ \t]+', ' ', text)

    # 3. Normalize paragraph breaks (max 2 consecutive line breaks)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 4. Clean line ends
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join([l for l in lines if l or l == ''])

    return text.strip()
