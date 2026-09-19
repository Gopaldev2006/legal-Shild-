from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.case import LegalCase
from app.services.cases.case_vector_store import case_vector_repo
from app.services.cases.case_loader import seed_public_academic_cases
from app.services.vector.embedding_service import generate_embedding


FALLBACK_NOT_AVAILABLE = "Not available in the indexed source."


class CaseRetrievalService:
    """
    Similar Legal Case Retrieval Service.
    Executes semantic similarity search over public academic case law dataset,
    enforcing metadata filtering and field grounding.
    """

    def search_similar_cases(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        court: Optional[str] = None,
        top_k: int = 5,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic similarity search over indexed case law dataset.
        Returns top-K matching cases with similarity scores and structured fields.
        """
        if not query or not query.strip():
            return []

        # Ensure public cases are seeded & indexed if store is empty
        if len(case_vector_repo.vectors) == 0 and db is not None:
            seed_public_academic_cases(db)

        # 1. Generate query embedding
        query_vector = generate_embedding(query.strip())

        # 2. Filter callback
        def case_filter(meta: Dict[str, Any]) -> bool:
            if jurisdiction and jurisdiction.strip():
                if jurisdiction.lower() not in meta.get("jurisdiction", "").lower():
                    return False
            if court and court.strip():
                if court.lower() not in meta.get("court", "").lower():
                    return False
            return True

        # 3. Perform similarity search
        raw_matches = case_vector_repo.search_cases(
            query_vector=query_vector,
            top_k=top_k * 3,  # fetch wider pool to deduplicate by case_id
            filter_fn=case_filter
        )

        seen_cases = set()
        deduped_results = []

        for match in raw_matches:
            cid = match.get("case_id")
            if not cid or cid in seen_cases:
                continue
            seen_cases.add(cid)

            # Extract fields with mandatory fallback
            title = match.get("title") or FALLBACK_NOT_AVAILABLE
            c_court = match.get("court") or FALLBACK_NOT_AVAILABLE
            c_date = match.get("date") or FALLBACK_NOT_AVAILABLE
            c_jurisdiction = match.get("jurisdiction") or FALLBACK_NOT_AVAILABLE
            facts = match.get("facts") or FALLBACK_NOT_AVAILABLE
            legal_issues = match.get("legal_issues") or FALLBACK_NOT_AVAILABLE
            arguments = match.get("arguments") or FALLBACK_NOT_AVAILABLE
            decision = match.get("decision") or FALLBACK_NOT_AVAILABLE
            source = match.get("source") or "Public Academic Legal Case Repository"
            source_ref = match.get("source_reference") or FALLBACK_NOT_AVAILABLE

            deduped_results.append({
                "case_id": cid,
                "title": title,
                "court": c_court,
                "date": c_date,
                "jurisdiction": c_jurisdiction,
                "similarity_score": match.get("score", 0.0),
                "relevant_facts": facts,
                "legal_issues": legal_issues,
                "arguments": arguments,
                "decision": decision,
                "source": source,
                "source_reference": source_ref
            })

            if len(deduped_results) >= top_k:
                break

        return deduped_results

    def get_case_details(self, case_id: str, db: Session) -> Dict[str, Any]:
        """
        Retrieves full case details from DB by case_id.
        """
        case_obj = db.query(LegalCase).filter(LegalCase.case_id == case_id).first()

        if not case_obj:
            return {
                "case_id": case_id,
                "title": FALLBACK_NOT_AVAILABLE,
                "court": FALLBACK_NOT_AVAILABLE,
                "date": FALLBACK_NOT_AVAILABLE,
                "jurisdiction": FALLBACK_NOT_AVAILABLE,
                "facts": FALLBACK_NOT_AVAILABLE,
                "legal_issues": FALLBACK_NOT_AVAILABLE,
                "arguments": FALLBACK_NOT_AVAILABLE,
                "decision": FALLBACK_NOT_AVAILABLE,
                "source": FALLBACK_NOT_AVAILABLE,
                "source_reference": FALLBACK_NOT_AVAILABLE
            }

        return {
            "case_id": case_obj.case_id,
            "title": case_obj.title or FALLBACK_NOT_AVAILABLE,
            "court": case_obj.court or FALLBACK_NOT_AVAILABLE,
            "date": case_obj.date or FALLBACK_NOT_AVAILABLE,
            "jurisdiction": case_obj.jurisdiction or FALLBACK_NOT_AVAILABLE,
            "facts": case_obj.facts or FALLBACK_NOT_AVAILABLE,
            "legal_issues": case_obj.legal_issues or FALLBACK_NOT_AVAILABLE,
            "arguments": case_obj.arguments or FALLBACK_NOT_AVAILABLE,
            "decision": case_obj.decision or FALLBACK_NOT_AVAILABLE,
            "source": case_obj.source or "Public Academic Legal Case Repository",
            "source_reference": case_obj.source_reference or FALLBACK_NOT_AVAILABLE
        }


case_retrieval_service = CaseRetrievalService()
