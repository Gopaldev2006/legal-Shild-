import os
import uuid
import hashlib
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.user import User, UserRole, VerificationStatus
from app.models.verification import VerificationRequest
from app.schemas.verification import VerificationResponse
from app.services.ocr import extract_text_from_file
from app.services.document.file_validator import FileValidator, FileValidationError
from app.core.config import settings

router = APIRouter()

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "verifications"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Verification credentials may also be image files (not just PDF/DOCX).
# We extend the allowed set here only for this endpoint.
_VERIFICATION_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp"}
_VERIFICATION_IMAGE_MAGIC = {
    ".png":  (b"\x89PNG",),
    ".jpg":  (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
}


@router.post("/request", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED, summary="Submit Professional Verification Request")
async def submit_verification_request(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits a professional verification request by uploading credentials.
    Performs file validation, cryptographic SHA-256 hashing, and OCR extraction.
    Updates user status to PENDING.
    """
    # ── Secure file validation (Phase 2) ────────────────────────────────────
    content = await file.read()

    # Sanitise filename and check extension against verification-specific allowlist
    try:
        _, ext = FileValidator.sanitise_filename(file.filename)
    except FileValidationError as fve:
        raise HTTPException(status_code=fve.http_status, detail=str(fve))

    if ext not in _VERIFICATION_ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(_VERIFICATION_ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=415,
            detail=f"File type '{ext}' is not allowed. Accepted types: {allowed}",
        )

    # Size check
    try:
        FileValidator.validate_size(content, max_size_mb=settings.MAX_VERIFICATION_SIZE_MB)
    except FileValidationError as fve:
        raise HTTPException(status_code=fve.http_status, detail=str(fve))

    # Magic-byte check — PDF and DOCX use existing signatures; images checked inline
    if ext in (".pdf", ".docx"):
        try:
            FileValidator.validate_magic_bytes(content, ext)
            if ext == ".docx":
                FileValidator.validate_docx_structure(content)
            elif ext == ".pdf":
                FileValidator.validate_pdf_structure(content)
        except FileValidationError as fve:
            raise HTTPException(status_code=fve.http_status, detail=str(fve))
    elif ext in _VERIFICATION_IMAGE_MAGIC:
        sigs = _VERIFICATION_IMAGE_MAGIC[ext]
        header = content[:8]
        if not any(header.startswith(sig) for sig in sigs):
            raise HTTPException(
                status_code=415,
                detail=f"Image file content does not match declared type '{ext}'. "
                       f"The file may be corrupt or disguised.",
            )

    # Keep original filename as metadata only; store under a UUID-based name
    safe_filename   = f"{uuid.uuid4().hex}{ext}"
    document_hash   = hashlib.sha256(content).hexdigest()
    original_name   = file.filename or f"credential{ext}"
    saved_file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(saved_file_path, "wb") as f:
        f.write(content)

    # Perform OCR extraction
    extracted_text = extract_text_from_file(saved_file_path, original_name)

    # 6. Update user verification status to PENDING
    current_user.verification_status = VerificationStatus.PENDING
    db.add(current_user)

    # 7. Create VerificationRequest record
    verification_req = VerificationRequest(
        user_id=current_user.id,
        document_path=saved_file_path,
        document_hash=document_hash,
        extracted_text=extracted_text,
        status=VerificationStatus.PENDING
    )
    db.add(verification_req)
    db.commit()
    db.refresh(verification_req)

    return verification_req


@router.get("/status", summary="Get User Verification Status & Latest Request")
def get_verification_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns current user's role, verification status, and latest request record if any.
    """
    latest_req = (
        db.query(VerificationRequest)
        .filter(VerificationRequest.user_id == current_user.id)
        .order_by(VerificationRequest.created_at.desc())
        .first()
    )

    return {
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role.value,
        "verification_status": current_user.verification_status.value,
        "latest_request": VerificationResponse.model_validate(latest_req) if latest_req else None
    }


@router.get("/document/{verification_id}", summary="Secure Document Download")
def download_verification_document(
    verification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Secure document download endpoint. Access restricted to document owner or ADMIN.
    """
    req = db.query(VerificationRequest).filter(VerificationRequest.id == verification_id).first()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification record not found")

    # Authorization Check: Owner or Admin
    if req.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You can only view your own verification documents"
        )

    if not os.path.exists(req.document_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical document file missing")

    return FileResponse(
        path=req.document_path,
        filename=os.path.basename(req.document_path),
        media_type="application/octet-stream"
    )
