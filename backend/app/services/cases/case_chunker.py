from typing import List, Dict, Any


def chunk_case(case_data: Dict[str, Any], chunk_size: int = 500) -> List[Dict[str, Any]]:
    """
    Splits case text fields into structured semantic chunks attached to case metadata.
    """
    case_id = case_data.get("case_id", "N/A")
    title = case_data.get("title", "")
    court = case_data.get("court", "")
    jurisdiction = case_data.get("jurisdiction", "")
    facts = case_data.get("facts", "")
    legal_issues = case_data.get("legal_issues", "")
    arguments = case_data.get("arguments", "")
    decision = case_data.get("decision", "")

    composite_text = f"Case Title: {title}. Court: {court}. Facts: {facts}. Legal Issues: {legal_issues}. Arguments: {arguments}. Decision: {decision}"

    words = composite_text.split()
    chunks = []
    chunk_idx = 0

    for i in range(0, len(words), chunk_size):
        chunk_words = words[i:i + chunk_size]
        chunk_str = " ".join(chunk_words)

        chunks.append({
            "chunk_id": f"{case_id}_chk_{chunk_idx}",
            "case_id": case_id,
            "title": title,
            "court": court,
            "jurisdiction": jurisdiction,
            "text": chunk_str,
            "chunk_index": chunk_idx
        })
        chunk_idx += 1

    return chunks
