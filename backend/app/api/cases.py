from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.api.deps import get_db, require_verified_legal_professional
from app.schemas.case import (
    CaseSearchRequest,
    CaseSearchResponse,
    CaseDetailResponse,
    ClusterGenerateRequest,
    ClusterGenerateResponse,
    ClusterItem,
    ClusterDetailResponse
)
from app.services.cases.case_retrieval_service import case_retrieval_service
from app.services.cases.case_clustering_service import case_clustering_service

router = APIRouter(prefix="/cases", tags=["Similar Legal Case Retrieval & Clustering"])


@router.post("/search", response_model=CaseSearchResponse)
def search_similar_cases(
    payload: CaseSearchRequest,
    current_user: User = Depends(require_verified_legal_professional),
    db: Session = Depends(get_db)
):
    """
    SIMILAR LEGAL CASE RETRIEVAL ENDPOINT
    Performs semantic similarity search over authorized public academic case law dataset.
    Restricted strictly to verified legal professionals or admins.
    """
    results = case_retrieval_service.search_similar_cases(
        query=payload.query,
        jurisdiction=payload.jurisdiction,
        court=payload.court,
        top_k=payload.top_k or 5,
        db=db
    )

    return {
        "results": results,
        "total": len(results)
    }


@router.post("/clusters/generate", response_model=ClusterGenerateResponse)
def generate_case_clusters(
    payload: ClusterGenerateRequest,
    current_user: User = Depends(require_verified_legal_professional),
    db: Session = Depends(get_db)
):
    """
    CASE CLUSTERING GENERATION ENDPOINT
    Executes K-Means semantic clustering over case embeddings for legal intelligence.
    Restricted strictly to verified legal professionals or admins.
    """
    num_k = payload.num_clusters or 3
    result = case_clustering_service.generate_clusters(num_clusters=num_k, db=db)
    return result


@router.get("/clusters", response_model=List[ClusterItem])
def get_case_clusters(
    current_user: User = Depends(require_verified_legal_professional),
    db: Session = Depends(get_db)
):
    """
    GET ALL CASE CLUSTERS ENDPOINT
    Returns summary statistics, representative cases, and topics for all generated clusters.
    Restricted strictly to verified legal professionals or admins.
    """
    clusters = case_clustering_service.get_clusters(db=db)
    return clusters


@router.get("/clusters/{cluster_id}", response_model=ClusterDetailResponse)
def get_cluster_details_by_id(
    cluster_id: int,
    current_user: User = Depends(require_verified_legal_professional),
    db: Session = Depends(get_db)
):
    """
    GET CLUSTER DETAILS ENDPOINT
    Returns complete case list and topic metadata for a specific cluster_id.
    Restricted strictly to verified legal professionals or admins.
    """
    details = case_clustering_service.get_cluster_details(cluster_id=cluster_id, db=db)
    return details


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case_by_id(
    case_id: str,
    current_user: User = Depends(require_verified_legal_professional),
    db: Session = Depends(get_db)
):
    """
    GET CASE DETAILS BY CASE ID ENDPOINT
    Retrieves complete structured case details (facts, legal issues, arguments, decision, source reference).
    Restricted strictly to verified legal professionals or admins.
    """
    case_detail = case_retrieval_service.get_case_details(case_id=case_id, db=db)
    return case_detail
