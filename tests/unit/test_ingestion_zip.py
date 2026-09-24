"""Unit tests for ZIP archive validation, extraction, and security protections."""

import io
import zipfile

import pytest

from backend.app.ingestion.zip import ZipIngester


def create_in_memory_zip(entries: dict[str, str | bytes]) -> bytes:
    """Helper to construct an in-memory zip file from a dict of relative_path -> content."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in entries.items():
            if isinstance(content, str):
                zf.writestr(path, content.encode("utf-8"))
            else:
                zf.writestr(path, content)
    return buf.getvalue()


def test_valid_zip_extraction():
    """Verify that a legitimate zip archive extracts properly into an isolated workspace."""
    zip_bytes = create_in_memory_zip(
        {
            "src/main.py": "print('hello')",
            "README.md": "# Project Title",
            "config.json": '{"env": "test"}',
        }
    )

    ingester = ZipIngester()
    source = ingester.ingest(zip_bytes, project_name="my_test_app")

    try:
        assert source.source_type == "zip"
        assert source.name == "my_test_app"
        assert source.extracted_path.exists()
        assert (source.extracted_path / "src" / "main.py").is_file()
        assert (source.extracted_path / "README.md").read_text(
            encoding="utf-8"
        ) == "# Project Title"
        assert source.metadata["file_count"] == 3
    finally:
        source.cleanup()
        assert not source.extracted_path.exists()


def test_zip_slip_traversal_attack_rejected():
    """Verify that zip archives with directory traversal paths are rejected."""
    malicious_zip = create_in_memory_zip(
        {
            "../../etc/passwd": "root:x:0:0:::",
            "normal.txt": "valid content",
        }
    )

    ingester = ZipIngester()
    with pytest.raises(ValueError, match="Path traversal"):
        ingester.ingest(malicious_zip)


def test_absolute_path_member_rejected():
    """Verify that archive members with absolute paths are rejected."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # Manually create ZipInfo with absolute path
        info = zipfile.ZipInfo(filename="/etc/shadow")
        zf.writestr(info, "hacked")
    zip_bytes = buf.getvalue()

    ingester = ZipIngester()
    with pytest.raises(ValueError, match="Dangerous absolute path"):
        ingester.ingest(zip_bytes)


def test_oversized_archive_rejected():
    """Verify that compressed archives exceeding maximum upload size are rejected."""
    small_data = b"x" * 2048
    zip_bytes = create_in_memory_zip({"data.txt": small_data})

    # Set strict max zip size limit of 100 bytes
    ingester = ZipIngester(max_zip_size_bytes=100)
    with pytest.raises(ValueError, match="exceeds maximum upload limit"):
        ingester.ingest(zip_bytes)


def test_oversized_extracted_content_rejected():
    """Verify that decompressing zip bombs or excessively large contents is aborted."""
    # 50 KB of repetitive text compresses to ~100 bytes in zip, but uncompresses to 50 KB
    large_payload = "A" * (50 * 1024)
    zip_bytes = create_in_memory_zip({"bomb.txt": large_payload})

    # Set extracted limit to 10 KB
    ingester = ZipIngester(max_extracted_size_bytes=10 * 1024)
    with pytest.raises(ValueError, match="exceeds limit"):
        ingester.ingest(zip_bytes)
