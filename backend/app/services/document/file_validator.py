"""
file_validator.py — Secure File Upload Validation
===================================================
Pure-stdlib validation pipeline. No external dependencies required.

Validation chain (in order):
  1. Filename sanitisation   — null bytes, path traversal, length
  2. Extension whitelist     — only .pdf and .docx accepted
  3. File size               — configurable MAX_DOCUMENT_SIZE_MB
  4. Empty file guard        — zero-byte files rejected
  5. Magic-byte signature    — file content must match declared type
  6. DOCX ZIP integrity      — DOCX must be a valid ZIP with Office XML entry

Usage:
    from app.services.document.file_validator import FileValidator, FileValidationError

    try:
        safe_ext = FileValidator.validate(
            filename=file.filename,
            content=content_bytes,
            max_size_mb=10,
        )
    except FileValidationError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc))
"""

import io
import re
import zipfile
from dataclasses import dataclass
from typing import Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Only these two types are accepted for legal documents
ALLOWED_EXTENSIONS: Tuple[str, ...] = (".pdf", ".docx")

# Magic byte signatures keyed by canonical extension
# PDF:  first 4 bytes must be  %PDF  (0x25 0x50 0x44 0x46)
# DOCX: first 4 bytes must be  PK\x03\x04  (ZIP local-file header)
MAGIC_SIGNATURES = {
    ".pdf":  (b"\x25\x50\x44\x46",),                   # %PDF
    ".docx": (b"\x50\x4B\x03\x04", b"\x50\x4B\x05\x06"),  # PK\x03\x04 or PK\x05\x06 (empty zip)
}

# The Office Open XML entry that must exist inside a valid DOCX ZIP
DOCX_REQUIRED_ENTRY = "word/document.xml"

# Characters forbidden in filenames (path separators, null byte, special chars)
_FORBIDDEN_FILENAME_RE = re.compile(r'[/\\:\*\?"<>\|\x00]')

# Maximum safe filename length (characters)
MAX_FILENAME_LENGTH = 255


# ─────────────────────────────────────────────────────────────────────────────
# Exception
# ─────────────────────────────────────────────────────────────────────────────

class FileValidationError(Exception):
    """
    Raised when a file fails any validation step.

    Attributes:
        http_status : HTTP status code to return to the client
        message     : Human-readable explanation (safe to show to the user)
    """
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status

    def __str__(self) -> str:
        return self.args[0]


# ─────────────────────────────────────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────────────────────────────────────

class FileValidator:
    """
    Stateless file validation utility for legal document uploads.

    All methods are static — no instantiation needed.
    """

    # ── 1. Filename sanitisation ──────────────────────────────────────────────

    @staticmethod
    def sanitise_filename(filename: str | None) -> Tuple[str, str]:
        """
        Validate and sanitise the original filename.

        Returns:
            (safe_basename, canonical_extension)  e.g. ("contract.pdf", ".pdf")

        Raises:
            FileValidationError on any suspicious filename pattern.
        """
        if not filename or not filename.strip():
            raise FileValidationError("Filename is missing or empty.")

        # Strip leading/trailing whitespace
        name = filename.strip()

        # Reject null bytes
        if "\x00" in name:
            raise FileValidationError("Filename contains null bytes.")

        # Reject path traversal sequences  (../ ..\\ etc.)
        if ".." in name:
            raise FileValidationError(
                "Filename contains path traversal sequences ('..')."
            )

        # Reject absolute paths (leading / or drive letters like C:\)
        if name.startswith("/") or name.startswith("\\") or (len(name) > 1 and name[1] == ":"):
            raise FileValidationError(
                "Filename must not be an absolute path."
            )

        # Strip any directory components — take only the final basename
        # e.g.  ../../etc/passwd.pdf  →  passwd.pdf
        basename = name.replace("\\", "/").split("/")[-1]

        # Reject forbidden characters
        if _FORBIDDEN_FILENAME_RE.search(basename):
            raise FileValidationError(
                f"Filename contains forbidden characters. "
                f"Only letters, numbers, spaces, hyphens, underscores and dots are allowed."
            )

        # Length check
        if len(basename) > MAX_FILENAME_LENGTH:
            raise FileValidationError(
                f"Filename too long ({len(basename)} chars). Maximum is {MAX_FILENAME_LENGTH}."
            )

        # Extract extension (lowercase)
        dot_pos = basename.rfind(".")
        if dot_pos < 0:
            raise FileValidationError("Filename has no extension.")

        ext = basename[dot_pos:].lower()
        return basename, ext

    # ── 2. Extension whitelist ────────────────────────────────────────────────

    @staticmethod
    def validate_extension(ext: str) -> None:
        """
        Ensure extension is in the allowed whitelist.

        Raises:
            FileValidationError with HTTP 415 (Unsupported Media Type)
        """
        if ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(ALLOWED_EXTENSIONS)
            raise FileValidationError(
                f"File type '{ext}' is not allowed. "
                f"Only {allowed} are accepted.",
                http_status=415,
            )

    # ── 3. File size ──────────────────────────────────────────────────────────

    @staticmethod
    def validate_size(content: bytes, max_size_mb: float) -> None:
        """
        Reject empty files and files exceeding max_size_mb.

        Raises:
            FileValidationError with HTTP 413 for oversized files.
            FileValidationError with HTTP 400 for empty files.
        """
        if len(content) == 0:
            raise FileValidationError("Uploaded file is empty.", http_status=400)

        max_bytes = int(max_size_mb * 1024 * 1024)
        if len(content) > max_bytes:
            actual_mb = len(content) / (1024 * 1024)
            raise FileValidationError(
                f"File size {actual_mb:.1f} MB exceeds the {max_size_mb:.0f} MB limit.",
                http_status=413,
            )

    # ── 4. Magic-byte signature ───────────────────────────────────────────────

    @staticmethod
    def validate_magic_bytes(content: bytes, ext: str) -> None:
        """
        Verify the file's magic bytes match the declared extension.

        Prevents renaming attacks (e.g. malware.exe → document.pdf).

        Raises:
            FileValidationError if magic bytes do not match.
        """
        signatures = MAGIC_SIGNATURES.get(ext)
        if signatures is None:
            # Extension already blocked by validate_extension; this is a safeguard
            raise FileValidationError(
                f"No magic-byte signature defined for '{ext}'.",
                http_status=415,
            )

        # Read the first 8 bytes for comparison
        header = content[:8]

        matched = any(header.startswith(sig) for sig in signatures)
        if not matched:
            raise FileValidationError(
                f"File content does not match the declared type '{ext}'. "
                f"The file may be corrupt or disguised as a different type.",
                http_status=415,
            )

    # ── 5. DOCX structural integrity ──────────────────────────────────────────

    @staticmethod
    def validate_docx_structure(content: bytes) -> None:
        """
        Verify that a DOCX file is a valid Office Open XML archive.

        A valid DOCX must:
          - Be a valid ZIP archive
          - Contain the entry 'word/document.xml'

        Raises:
            FileValidationError if the archive is corrupt or missing required entries.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(content), "r") as zf:
                names = zf.namelist()
                if DOCX_REQUIRED_ENTRY not in names:
                    raise FileValidationError(
                        f"DOCX file is missing required entry '{DOCX_REQUIRED_ENTRY}'. "
                        f"The file may be corrupt or not a valid Word document.",
                        http_status=415,
                    )
        except zipfile.BadZipFile:
            raise FileValidationError(
                "DOCX file is not a valid ZIP archive. "
                "The file may be corrupt or disguised as a Word document.",
                http_status=415,
            )
        except FileValidationError:
            raise
        except Exception:
            raise FileValidationError(
                "DOCX file could not be validated. The file may be corrupt.",
                http_status=415,
            )

    # ── 5b. PDF minimal structural check ─────────────────────────────────────

    @staticmethod
    def validate_pdf_structure(content: bytes) -> None:
        """
        Minimal PDF structural validation.

        Checks:
          - Has %PDF header (already verified by magic bytes)
          - Contains %%EOF marker somewhere in the last 1 KB
          - File is at least 100 bytes (filters out stub/empty PDF shells)

        Does NOT parse the full PDF — that is left to pypdf during extraction.

        Raises:
            FileValidationError if the file fails structural checks.
        """
        if len(content) < 100:
            raise FileValidationError(
                "PDF file is too small to be a valid document (< 100 bytes).",
                http_status=415,
            )

        # Check for %%EOF marker in the last 1024 bytes
        tail = content[-1024:]
        if b"%%EOF" not in tail and b"%EOF" not in tail:
            raise FileValidationError(
                "PDF file appears to be truncated or corrupt (missing %%EOF marker).",
                http_status=415,
            )

    # ── Public API ────────────────────────────────────────────────────────────

    @classmethod
    def validate(
        cls,
        filename: str | None,
        content: bytes,
        max_size_mb: float = 10.0,
    ) -> str:
        """
        Run the complete validation pipeline in order.

        Pipeline:
          1. Sanitise filename  →  extract safe basename and extension
          2. Validate extension →  whitelist check
          3. Validate size      →  empty / oversized
          4. Validate magic     →  content matches declared type
          5. Type-specific check → DOCX ZIP integrity / PDF EOF

        Parameters:
            filename     : original filename from upload (may be None)
            content      : raw bytes of the uploaded file
            max_size_mb  : maximum allowed file size in MB

        Returns:
            Canonical extension string, e.g. ".pdf" or ".docx"

        Raises:
            FileValidationError on any failed check.
        """
        # Step 1 — filename
        _, ext = cls.sanitise_filename(filename)

        # Step 2 — extension whitelist
        cls.validate_extension(ext)

        # Step 3 — size (includes empty check)
        cls.validate_size(content, max_size_mb)

        # Step 4 — magic bytes
        cls.validate_magic_bytes(content, ext)

        # Step 5 — type-specific structural check
        if ext == ".docx":
            cls.validate_docx_structure(content)
        elif ext == ".pdf":
            cls.validate_pdf_structure(content)

        return ext
