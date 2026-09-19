import re
import numpy as np
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.case import LegalCase
from app.services.cases.case_loader import seed_public_academic_cases
from app.services.cases.case_vector_store import case_vector_repo
from app.services.vector.embedding_service import generate_embedding

AI_CLUSTERING_DISCLAIMER = (
    "AI-Assisted Semantic Grouping Notice: Clustering represents an AI-assisted semantic "
    "grouping mechanism based on mathematical embedding proximity. It does not determine "
    "legal similarity or binding judicial precedent with certainty."
)


class CaseClusteringService:
    """
    Legal Case Clustering Service.
    Groups semantically similar cases using K-Means clustering over case embeddings.
    Extracts representative topics, cluster statistics, and case-to-cluster mappings.
    """

    def generate_clusters(self, num_clusters: int = 3, db: Optional[Session] = None) -> Dict[str, Any]:
        """
        Executes K-Means clustering over all indexed legal cases.
        Updates DB case records with assigned cluster_id.
        """
        if db is None:
            return {"status": "error", "message": "Database session required"}

        # 1. Ensure cases exist
        cases = db.query(LegalCase).all()
        if not cases or len(cases) < 2:
            seed_public_academic_cases(db)
            cases = db.query(LegalCase).all()

        if not cases:
            return {"status": "empty", "message": "No cases available for clustering", "clusters": []}

        # Clamp num_clusters to not exceed number of cases
        k = max(1, min(num_clusters, len(cases)))

        # 2. Extract feature matrix (case embeddings)
        case_vectors = []
        for c in cases:
            text = f"{c.title} {c.jurisdiction} {c.facts} {c.legal_issues} {c.decision}"
            vec = generate_embedding(text)
            vec_np = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(vec_np)
            if norm > 0:
                vec_np = vec_np / norm
            case_vectors.append(vec_np)

        X = np.vstack(case_vectors)

        # 3. Perform K-Means Clustering
        labels = self._k_means_clustering(X, k=k, max_iters=20)

        # 4. Update LegalCase records in DB
        for case_obj, cluster_label in zip(cases, labels):
            case_obj.cluster_id = int(cluster_label)

        db.commit()

        # 5. Build cluster summaries
        cluster_summaries = self._build_cluster_summaries(db, k)

        return {
            "status": "success",
            "clusters_generated": k,
            "total_cases_clustered": len(cases),
            "disclaimer": AI_CLUSTERING_DISCLAIMER,
            "clusters": cluster_summaries
        }

    def _k_means_clustering(self, X: np.ndarray, k: int, max_iters: int = 20) -> np.ndarray:
        """
        Pure NumPy K-Means clustering implementation.
        """
        n_samples = X.shape[0]

        # Initial centroids chosen deterministically across sample range
        indices = np.linspace(0, n_samples - 1, k, dtype=int)
        centroids = X[indices].copy()

        labels = np.zeros(n_samples, dtype=int)

        for _ in range(max_iters):
            # Compute distance matrix (Cosine distance = 1 - dot product for normalized vectors)
            distances = 1.0 - np.dot(X, centroids.T)
            new_labels = np.argmin(distances, axis=1)

            if np.array_equal(labels, new_labels):
                break

            labels = new_labels

            # Recompute centroids
            for c_idx in range(k):
                members = X[labels == c_idx]
                if len(members) > 0:
                    c_mean = np.mean(members, axis=0)
                    c_norm = np.linalg.norm(c_mean)
                    if c_norm > 0:
                        c_mean = c_mean / c_norm
                    centroids[c_idx] = c_mean

        return labels

    def _build_cluster_summaries(self, db: Session, k: int) -> List[Dict[str, Any]]:
        """
        Extracts representative cases, common legal topics, and statistics for each cluster.
        """
        cluster_summaries = []

        for cid in range(k):
            cases_in_cluster = db.query(LegalCase).filter(LegalCase.cluster_id == cid).all()
            if not cases_in_cluster:
                continue

            # Extract representative case titles
            rep_titles = [c.title for c in cases_in_cluster[:3]]

            # Extract common topics/keywords from jurisdictions & legal issues
            all_topics_text = " ".join([f"{c.jurisdiction} {c.court}" for c in cases_in_cluster])
            keywords = set(re.findall(r"\b[A-[Z][a-z]{3,}\b", all_topics_text))
            keywords = [kw for kw in keywords if kw not in {"India", "Supreme", "Court", "State", "Union"}]

            topics = list(keywords)[:4] if keywords else ["Constitutional Law", "Commercial Precedents"]

            cluster_summaries.append({
                "cluster_id": cid,
                "case_count": len(cases_in_cluster),
                "topics": topics,
                "representative_cases": rep_titles,
                "disclaimer": AI_CLUSTERING_DISCLAIMER
            })

        return cluster_summaries

    def get_clusters(self, db: Session) -> List[Dict[str, Any]]:
        """
        Retrieves summary list of all existing clusters.
        """
        distinct_clusters = db.query(LegalCase.cluster_id).distinct().all()
        cluster_ids = sorted([c[0] for c in distinct_clusters if c[0] is not None])

        if not cluster_ids:
            # Trigger initial clustering if none exists
            res = self.generate_clusters(num_clusters=3, db=db)
            return res.get("clusters", [])

        return self._build_cluster_summaries(db, len(cluster_ids))

    def get_cluster_details(self, cluster_id: int, db: Session) -> Dict[str, Any]:
        """
        Retrieves detailed cases for a specific cluster_id.
        """
        cases_in_cluster = db.query(LegalCase).filter(LegalCase.cluster_id == cluster_id).all()

        case_list = []
        for c in cases_in_cluster:
            case_list.append({
                "case_id": c.case_id,
                "title": c.title,
                "court": c.court,
                "date": c.date,
                "jurisdiction": c.jurisdiction,
                "similarity_score": 1.0,  # Cluster membership indicator
                "relevant_facts": c.facts,
                "legal_issues": c.legal_issues,
                "arguments": c.arguments,
                "decision": c.decision,
                "source": c.source,
                "source_reference": c.source_reference
            })

        topics = list(set([c.jurisdiction for c in cases_in_cluster if c.jurisdiction]))

        return {
            "cluster_id": cluster_id,
            "case_count": len(case_list),
            "topics": topics,
            "cases": case_list,
            "disclaimer": AI_CLUSTERING_DISCLAIMER
        }


case_clustering_service = CaseClusteringService()
