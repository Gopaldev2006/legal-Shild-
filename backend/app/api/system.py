"""
System Metrics & Audit Compliance API Router.

Provides API endpoints for system performance benchmarking and audit compliance.

Access:
  /system/metrics          — any authenticated user (own context)
  /system/compliance-report — authenticated; admins see all, others see own data
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.api.deps import get_current_user, get_db          # ← from deps, not auth
from app.models.user import User, UserRole
from app.services.system import benchmark_engine, audit_compliance_service
from app.services.vector.retrieval_service import UserContext

router = APIRouter(prefix="/system", tags=["System & Audit Compliance"])


@router.get("/metrics", response_model=Dict[str, Any])
def get_system_metrics(
    query: str = "Sample benchmark query",
    current_user: User = Depends(get_current_user),   # 401 if unauthenticated
) -> Dict[str, Any]:
    """
    Returns system performance benchmarks, RAM usage, and component latency.
    Accessible to any authenticated user (results are scoped to their context).
    """
    user_context = UserContext(
        user_id=current_user.id,
        role=current_user.role.value,
    )
    return benchmark_engine.benchmark_rag_performance(
        query_text=query,
        user_context=user_context,
    )


@router.get("/compliance-report", response_model=Dict[str, Any])
def get_compliance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),   # 401 if unauthenticated
) -> Dict[str, Any]:
    """
    Returns security audit compliance report.
    - ADMIN: system-wide report (all users)
    - Everyone else: personal audit metrics only
    """
    target_user_id = None if current_user.role == UserRole.ADMIN else current_user.id
    return audit_compliance_service.generate_compliance_report(
        db=db,
        user_id=target_user_id,
    )
