from fastapi import APIRouter
from app.api import health, auth, verification, admin, documents, vector, rag, cases, system, chat

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Access Control"])
api_router.include_router(verification.router, prefix="/verification", tags=["Professional Verification"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Management"])
api_router.include_router(documents.router, prefix="/documents", tags=["Document Processing & Pipeline"])
api_router.include_router(vector.router, prefix="/vector", tags=["Vector Store & Retrieval"])
api_router.include_router(rag.router, tags=["Secure RAG Pipeline"])
api_router.include_router(cases.router, tags=["Similar Legal Case Retrieval"])
api_router.include_router(system.router, tags=["System & Audit Compliance"])
api_router.include_router(chat.router, tags=["Persistent Chat"])

