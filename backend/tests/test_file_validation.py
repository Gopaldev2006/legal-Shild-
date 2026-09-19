"""
test_file_validation.py — Phase 2: Secure File Validation Tests
================================================================
11 test cases covering the complete FileValidator pipeline.

Test cases:
  TC-01  valid PDF             → passes all checks, returns ".pdf"
  TC-02  valid DOCX            → passes all checks, returns ".docx"
  TC-03  oversized file        → HTTP 413
  TC-04  invalid extension     → HTTP 415 (.exe, .txt, .zip, etc.)
  TC-05  fake PDF (EXE bytes)  → HTTP 415 (magic-byte mismatch)
  TC-06  fake DOCX (EXE bytes) → HTTP 415 (magic-byte mismatch)
  TC-07  path traversal fname  → HTTP 400 (filename sanitisation)
  TC-08  empty file            → HTTP 400
  TC-09  malformed DOCX        → HTTP 415 (invalid ZIP / missing word/document.xml)
  TC-10  null-byte filename    → HTTP 400
  TC-11  truncated / corrupt PDF → HTTP 415 (missing %%EOF)

Run:
    cd backend
    python -m pytest tests/test_file_validation.py -v
"""

import io
import zipfile
import pytest

from app.services.document.file_validator import (
    FileValidator,
    FileValidationError,
    DOCX_REQUIRED_ENTRY,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — minimal valid file fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_minimal_pdf() -> bytes:
    """Return the smallest byte sequence that passes all PDF validation checks."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000009 00000 n \n"
        b"trailer\n<< /Size 2 /Root 1 0 R >>\n"
        b"startxref\n9\n"
        b"%%EOF"
    )


def _make_minimal_docx() -> bytes:
    """Return the smallest byte sequence that passes all DOCX validation checks."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Minimal [Content_Types].xml
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml"'
            ' ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        # Minimal word/document.xml — required entry
        zf.writestr(
            DOCX_REQUIRED_ENTRY,
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Test</w:t></w:r></w:p></w:body>"
            "</w:document>",
        )
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# TC-01  Valid PDF
# ─────────────────────────────────────────────────────────────────────────────

class TestValidPDF:
    def test_valid_pdf_passes_all_checks(self):
        content = _make_minimal_pdf()
        ext = FileValidator.validate(
            filename="employment_contract.pdf",
            content=content,
            max_size_mb=10.0,
        )
        assert ext == ".pdf", "Expected '.pdf' returned for a valid PDF"

    def test_valid_pdf_case_insensitive_extension(self):
        """Extension matching must be case-insensitive (.PDF → .pdf)."""
        content = _make_minimal_pdf()
        ext = FileValidator.validate(
            filename="CONTRACT.PDF",
            content=content,
            max_size_mb=10.0,
        )
        assert ext == ".pdf"


# ─────────────────────────────────────────────────────────────────────────────
# TC-02  Valid DOCX
# ─────────────────────────────────────────────────────────────────────────────

class TestValidDOCX:
    def test_valid_docx_passes_all_checks(self):
        content = _make_minimal_docx()
        ext = FileValidator.validate(
            filename="nda_agreement.docx",
            content=content,
            max_size_mb=10.0,
        )
        assert ext == ".docx", "Expected '.docx' returned for a valid DOCX"


# ─────────────────────────────────────────────────────────────────────────────
# TC-03  Oversized file
# ─────────────────────────────────────────────────────────────────────────────

class TestOversizedFile:
    def test_file_exceeding_limit_raises_413(self):
        # Build a valid PDF header then pad it to 11 MB
        base   = _make_minimal_pdf()
        padded = base + b"\x00" * (11 * 1024 * 1024)

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="big.pdf",
                content=padded,
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 413
        assert "exceeds" in str(exc_info.value).lower()

    def test_file_exactly_at_limit_passes(self):
        """A file exactly at the limit (not over) must pass."""
        base      = _make_minimal_pdf()
        max_bytes = int(10.0 * 1024 * 1024)
        # Pad to exactly max_bytes (content is mostly zeros after the PDF trailer)
        padded    = base.rstrip(b"%%EOF") + b"\x00" * (max_bytes - len(base)) + b"%%EOF"
        # Should not raise
        FileValidator.validate(filename="exactly_10mb.pdf", content=padded, max_size_mb=10.0)


# ─────────────────────────────────────────────────────────────────────────────
# TC-04  Invalid extension
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidExtension:
    @pytest.mark.parametrize("bad_name", [
        "malware.exe",
        "script.js",
        "archive.zip",
        "image.png",
        "data.csv",
        "document.txt",   # .txt was in old allowlist — must now be rejected
        "no_extension",
    ])
    def test_disallowed_extension_raises_415(self, bad_name):
        content = b"\x00" * 100  # content irrelevant for extension check

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename=bad_name,
                content=content,
                max_size_mb=10.0,
            )

        # Extension check returns 415; filename-no-extension returns 400
        assert exc_info.value.http_status in (400, 415)


# ─────────────────────────────────────────────────────────────────────────────
# TC-05  Fake PDF (magic-byte mismatch)
# ─────────────────────────────────────────────────────────────────────────────

class TestFakePDF:
    def test_exe_renamed_to_pdf_rejected(self):
        """An EXE file renamed to .pdf must fail magic-byte check."""
        # MZ header — Windows PE executable
        exe_content = b"\x4D\x5A\x90\x00" + b"\x00" * 200 + b"%%EOF"

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="totally_a_pdf.pdf",
                content=exe_content,
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 415
        assert "content does not match" in str(exc_info.value).lower() \
               or "corrupt" in str(exc_info.value).lower() \
               or "disguised" in str(exc_info.value).lower()

    def test_random_bytes_as_pdf_rejected(self):
        """Random bytes with .pdf extension must be rejected."""
        garbage = b"\xDE\xAD\xBE\xEF" * 50 + b"%%EOF"

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(filename="fake.pdf", content=garbage, max_size_mb=10.0)

        assert exc_info.value.http_status == 415


# ─────────────────────────────────────────────────────────────────────────────
# TC-06  Fake DOCX (magic-byte mismatch)
# ─────────────────────────────────────────────────────────────────────────────

class TestFakeDOCX:
    def test_exe_renamed_to_docx_rejected(self):
        """An EXE renamed to .docx must fail magic-byte check."""
        exe_content = b"\x4D\x5A\x90\x00" + b"\x00" * 200

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="contract.docx",
                content=exe_content,
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 415

    def test_zip_without_word_document_xml_rejected(self):
        """A ZIP file (correct magic bytes) lacking word/document.xml must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("some_other_file.xml", "<data/>")
        fake_docx = buf.getvalue()

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="fake_docx.docx",
                content=fake_docx,
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 415
        assert "word/document.xml" in str(exc_info.value) \
               or "missing" in str(exc_info.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-07  Path traversal filenames
# ─────────────────────────────────────────────────────────────────────────────

class TestPathTraversal:
    @pytest.mark.parametrize("bad_name", [
        "../../etc/passwd.pdf",
        "..\\..\\windows\\system32\\evil.pdf",
        "/absolute/path/file.pdf",
        "C:\\Windows\\System32\\evil.docx",
    ])
    def test_path_traversal_filename_rejected(self, bad_name):
        content = _make_minimal_pdf()

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename=bad_name,
                content=content,
                max_size_mb=10.0,
            )

        # All path-traversal/absolute-path cases must be blocked.
        # The exact status code depends on whether rejection happens at
        # the filename stage (400) or later content stage (415) —
        # both outcomes are correct because the upload is refused.
        assert exc_info.value.http_status in (400, 415)


# ─────────────────────────────────────────────────────────────────────────────
# TC-08  Empty file
# ─────────────────────────────────────────────────────────────────────────────

class TestEmptyFile:
    def test_zero_byte_file_raises_400(self):
        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="empty.pdf",
                content=b"",
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 400
        assert "empty" in str(exc_info.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-09  Malformed DOCX (corrupt ZIP)
# ─────────────────────────────────────────────────────────────────────────────

class TestMalformedDOCX:
    def test_truncated_zip_rejected(self):
        """A DOCX file that starts with PK magic but is not a valid ZIP."""
        # PK magic followed by garbage — not a real ZIP
        corrupt = b"\x50\x4B\x03\x04" + b"\xFF\xFE\xFD" * 30

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="corrupt.docx",
                content=corrupt,
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 415
        assert "zip" in str(exc_info.value).lower() \
               or "corrupt" in str(exc_info.value).lower() \
               or "valid" in str(exc_info.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-10  Null-byte filename
# ─────────────────────────────────────────────────────────────────────────────

class TestNullByte:
    def test_null_byte_in_filename_rejected(self):
        content = _make_minimal_pdf()

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="contract\x00.pdf",
                content=content,
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 400
        assert "null" in str(exc_info.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-11  Truncated / corrupt PDF (missing %%EOF)
# ─────────────────────────────────────────────────────────────────────────────

class TestTruncatedPDF:
    def test_pdf_missing_eof_marker_rejected(self):
        """A PDF with correct magic bytes but no %%EOF must be rejected."""
        truncated = b"%PDF-1.4\n" + b"some content\n" * 20
        # Deliberately no %%EOF

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="truncated.pdf",
                content=truncated,
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 415
        assert "truncated" in str(exc_info.value).lower() \
               or "corrupt" in str(exc_info.value).lower() \
               or "eof" in str(exc_info.value).lower()

    def test_pdf_too_small_rejected(self):
        """A PDF stub smaller than 100 bytes must be rejected."""
        stub = b"%PDF-1.4\n%%EOF"   # Valid header + EOF but < 100 bytes

        with pytest.raises(FileValidationError) as exc_info:
            FileValidator.validate(
                filename="stub.pdf",
                content=stub,
                max_size_mb=10.0,
            )

        assert exc_info.value.http_status == 415
        assert "too small" in str(exc_info.value).lower() \
               or "100" in str(exc_info.value)
