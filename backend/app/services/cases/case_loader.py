from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.case import LegalCase
from app.services.cases.case_cleaner import clean_case_text
from app.services.cases.case_chunker import chunk_case
from app.services.cases.case_vector_store import case_vector_repo
from app.services.vector.embedding_service import generate_embedding


PUBLIC_ACADEMIC_CASE_DATASET: List[Dict[str, Any]] = [
    {
        "case_id": "CASE-2024-001",
        "title": "BALCO Employees Union v. Union of India & Ors.",
        "court": "Supreme Court of India",
        "date": "2001-12-10",
        "jurisdiction": "India / Constitutional & Economic Law",
        "facts": "Petitioner trade union challenged the disinvestment policy of the Government of India regarding Bharat Aluminium Company Limited (BALCO), claiming violation of workers' fundamental rights under Article 21 and statutory labor rights.",
        "legal_issues": "Whether economic policy decisions of disinvestment are subject to judicial review under Article 32 of the Constitution, and whether workers have a right to prior consultation.",
        "arguments": "Petitioners argued disinvestment adversely affected job security and constitutional guarantees under Article 14 and 21. Respondents submitted economic policy decisions fall within executive prerogative and courts should exercise judicial restraint.",
        "decision": "Dismissed the petition. Held that courts will not interfere with economic policy matters unless demonstrated to be arbitrary, mala fide, or unconstitutional. Prior consultation with workers was not statutory mandatory.",
        "source": "Public Academic Legal Repository (AIR 2002 SC 350)",
        "source_reference": "AIR 2002 SC 350 | (2002) 2 SCC 333"
    },
    {
        "case_id": "CASE-2024-002",
        "title": "Kesavananda Bharati Sripadagalvaru v. State of Kerala",
        "court": "Supreme Court of India",
        "date": "1973-04-24",
        "jurisdiction": "India / Constitutional Law",
        "facts": "Religious math head challenged Kerala Land Reforms Amendment Act 1969 restricting property rights of religious institutions under Article 26 of the Constitution of India.",
        "legal_issues": "Extent of Parliament's amending power under Article 368 of the Constitution and whether fundamental rights can be abrogated completely.",
        "arguments": "Petitioners asserted Parliament cannot alter the essential identity and core features of the Constitution. Respondents contended Parliament possesses unlimited amending power under Article 368.",
        "decision": "Landmark 7:6 majority verdict established the Basic Structure Doctrine. Parliament has wide power to amend the Constitution but cannot alter or destroy its 'Basic Structure' (judicial review, rule of law, secularism, federalism).",
        "source": "Public Academic Legal Repository (AIR 1973 SC 1461)",
        "source_reference": "AIR 1973 SC 1461 | (1973) 4 SCC 225"
    },
    {
        "case_id": "CASE-2024-003",
        "title": "Bharat Aluminium Co. v. Kaiser Aluminium Technical Services Inc. (BALCO 2012)",
        "court": "Supreme Court of India",
        "date": "2012-09-06",
        "jurisdiction": "India / International Commercial Arbitration",
        "facts": "Dispute arose out of an agreement executed in 1993 for supply of equipment with arbitration seat designated in London. Indian party sought interim injunction under Section 9 of the Arbitration and Conciliation Act 1996.",
        "legal_issues": "Whether Part I of the Indian Arbitration and Conciliation Act 1996 applies to foreign-seated arbitrations.",
        "arguments": "Appellant relied on Bhatia International contending Part I applies unless expressly excluded. Respondent argued Part I applies strictly to arbitrations held inside India.",
        "decision": "Constitution Bench overruled Bhatia International prospectively. Held that Part I of the 1996 Act does not apply to foreign-seated arbitrations. Indian courts cannot grant interim relief under Section 9 for foreign arbitrations.",
        "source": "Public Academic Legal Repository ((2012) 9 SCC 552)",
        "source_reference": "(2012) 9 SCC 552 | 2012 STPL SC 740"
    },
    {
        "case_id": "CASE-2024-004",
        "title": "M/s N.N. Global Mercantile Pvt. Ltd. v. M/s Indo Unique Flame Ltd.",
        "court": "Supreme Court of India",
        "date": "2023-04-25",
        "jurisdiction": "India / Commercial Arbitration & Stamp Law",
        "facts": "Contract containing an arbitration clause was unstamped under the Maharashtra Stamp Act. Sub-contractor sought appointment of arbitrator under Section 11 of the 1996 Act.",
        "legal_issues": "Whether an unstamped commercial contract containing an arbitration clause is enforceable in law at the Section 11 stage.",
        "arguments": "Petitioner argued arbitration agreement is separable and valid despite stamping defects. Respondent submitted an unstamped contract is inadmissible in evidence under Stamp Act and cannot be acted upon.",
        "decision": "5-Judge Constitution Bench held 3:2 that an unstamped or insufficiently stamped agreement is not enforceable in law until stamped, preventing Section 11 arbitrator appointment until impounded and stamped.",
        "source": "Public Academic Legal Repository (2023 INSC 420)",
        "source_reference": "(2023) 7 SCC 1 | 2023 INSC 420"
    },
    {
        "case_id": "CASE-2024-005",
        "title": "M.C. Mehta & Anr. v. Union of India (Oleum Gas Leak Case)",
        "court": "Supreme Court of India",
        "date": "1986-12-20",
        "jurisdiction": "India / Environmental Law & Tort",
        "facts": "Oleum gas leak occurred from Shriram Food and Fertilizers plant in Delhi during pendency of public interest litigation, causing death and severe illness to citizens.",
        "legal_issues": "Standard of liability for hazardous and inherently dangerous industrial enterprises operating in populated areas.",
        "arguments": "Shriram argued strict liability under Rylands v. Fletcher applied with standard exceptions (act of God, third-party act). Petitioner urged absolute liability without exceptions.",
        "decision": "Formulated the doctrine of Absolute Liability. Hazardous industrial units owe an absolute and non-delegable duty to the community. Liability is absolute without exceptions, and compensation is correlated to enterprise capacity.",
        "source": "Public Academic Legal Repository (AIR 1987 SC 1086)",
        "source_reference": "AIR 1987 SC 1086 | (1987) 1 SCC 395"
    }
]


def seed_public_academic_cases(db: Session) -> int:
    """
    Seeds initial public academic legal case dataset into SQLite DB and indexes case vectors.
    """
    seeded_count = 0

    for case_data in PUBLIC_ACADEMIC_CASE_DATASET:
        existing = db.query(LegalCase).filter(LegalCase.case_id == case_data["case_id"]).first()
        if not existing:
            new_case = LegalCase(
                case_id=case_data["case_id"],
                title=clean_case_text(case_data["title"]),
                court=clean_case_text(case_data["court"]),
                date=clean_case_text(case_data["date"]),
                jurisdiction=clean_case_text(case_data["jurisdiction"]),
                facts=clean_case_text(case_data["facts"]),
                legal_issues=clean_case_text(case_data["legal_issues"]),
                arguments=clean_case_text(case_data["arguments"]),
                decision=clean_case_text(case_data["decision"]),
                source=clean_case_text(case_data["source"]),
                source_reference=clean_case_text(case_data["source_reference"])
            )
            db.add(new_case)
            db.commit()
            db.refresh(new_case)
            seeded_count += 1
        else:
            new_case = existing

        # Vector Indexing for Case
        chunks = chunk_case(case_data)
        for chk in chunks:
            vector = generate_embedding(chk["text"])
            case_vector_repo.add_case_vector(
                vector=vector,
                metadata={
                    "case_id": case_data["case_id"],
                    "db_id": new_case.id,
                    "title": new_case.title,
                    "court": new_case.court,
                    "date": new_case.date,
                    "jurisdiction": new_case.jurisdiction,
                    "facts": new_case.facts,
                    "legal_issues": new_case.legal_issues,
                    "arguments": new_case.arguments,
                    "decision": new_case.decision,
                    "source": new_case.source,
                    "source_reference": new_case.source_reference,
                    "text": chk["text"]
                }
            )

    return seeded_count
