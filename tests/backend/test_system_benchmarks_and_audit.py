"""
Pytest Verification Suite for Phase 15 System Benchmarks & Audit Compliance Engine.

Tests:
1. System performance benchmarking (latency split & RAM usage measurement)
2. Audit compliance report generation & security metric aggregation
3. /api/v1/system/metrics endpoint
4. /api/v1/system/compliance-report endpoint
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.orm import Session
from app.main import app
from app.models.user import User, UserRole, VerificationStatus
from app.core.security import get_password_hash
from app.services.system import benchmark_engine, audit_compliance_service
from app.services.vector.retrieval_service import UserContext


def test_system_benchmark_performance_measurement():
    """1. Verify benchmark engine accurately measures latency split and memory usage."""
    user_context = UserContext(user_id=1, role="LEGAL_PROFESSIONAL")
    
    benchmark = benchmark_engine.benchmark_rag_performance(
        query_text="What are the statutory limitation periods?",
        user_context=user_context,
        top_k=3
    )

    assert benchmark["status"] == "COMPLETED"
    assert "performance_metrics" in benchmark
    metrics = benchmark["performance_metrics"]
    
    assert "screening_latency_ms" in metrics
    assert "retrieval_latency_ms" in metrics
    assert "prompt_build_latency_ms" in metrics
    assert "slm_generation_latency_seconds" in metrics
    assert "total_end_to_end_latency_seconds" in metrics
    assert metrics["final_memory_mb"] > 0
    assert benchmark["system_status"]["memory_healthy"] is True


def test_audit_compliance_report_generation(db: Session):
    """2. Verify security audit compliance report aggregates security metrics accurately."""
    user = User(
        name="Adv. Compliance Officer",
        email="compliance_officer@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    report = audit_compliance_service.generate_compliance_report(db=db, user_id=user.id)

    assert report["compliance_status"] == "COMPLIANT"
    assert "compliance_score_percent" in report
    assert "summary_totals" in report
    assert "prompt_injection_defense" in report
    assert "data_leakage_protection" in report
    assert "compliance_certification" in report


@pytest.mark.asyncio
async def test_system_metrics_api_endpoint(db: Session):
    """3. Verify GET /api/v1/system/metrics endpoint."""
    user = User(
        name="Adv. Metric User",
        email="metric_user@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "metric_user@example.com", "password": "pass123"})).json()["access_token"]

        res = await ac.get(
            "/api/v1/system/metrics?query=test+query",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "COMPLETED"
        assert "performance_metrics" in data


@pytest.mark.asyncio
async def test_compliance_report_api_endpoint(db: Session):
    """4. Verify GET /api/v1/system/compliance-report endpoint."""
    user = User(
        name="Adv. Report User",
        email="report_user@example.com",
        password_hash=get_password_hash("pass123"),
        role=UserRole.LEGAL_PROFESSIONAL,
        verification_status=VerificationStatus.VERIFIED
    )
    db.add(user)
    db.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        token = (await ac.post("/api/v1/auth/login", json={"email": "report_user@example.com", "password": "pass123"})).json()["access_token"]

        res = await ac.get(
            "/api/v1/system/compliance-report",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert res.status_code == 200
        data = res.json()
        assert data["compliance_status"] == "COMPLIANT"
        assert "summary_totals" in data
