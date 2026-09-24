"""ZIP project ingestion module with Zip-Slip protection and zip-bomb mitigation."""

import io
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import BinaryIO

from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.ingestion.models import ProjectSource

logger = get_logger(__name__)


class ZipIngester:
    """Safely validates and extracts ZIP archives into isolated workspaces."""

    def __init__(
        self,
        max_zip_size_bytes: int | None = None,
        max_extracted_size_bytes: int | None = None,
        max_files_count: int | None = None,
        temp_dir: Path | None = None,
    ) -> None:
        self.max_zip_size = max_zip_size_bytes or settings.MAX_ZIP_UPLOAD_SIZE_BYTES
        self.max_extracted_size = max_extracted_size_bytes or settings.MAX_EXTRACTED_SIZE_BYTES
        self.max_files_count = max_files_count or settings.MAX_FILES_COUNT
        self.temp_root = temp_dir or (
            Path(settings.TEMP_WORKSPACE_DIR) if settings.TEMP_WORKSPACE_DIR else None
        )

    def ingest(
        self,
        source: Path | str | bytes | BinaryIO,
        project_name: str | None = None,
    ) -> ProjectSource:
        """Safely extract ZIP archive into an isolated temporary workspace."""
        file_obj, archive_size, inferred_name = self._prepare_source(source)
        name = project_name or inferred_name or "uploaded_project"

        if archive_size > self.max_zip_size:
            mb = archive_size / (1024 * 1024)
            max_mb = self.max_zip_size / (1024 * 1024)
            raise ValueError(
                f"Archive size ({mb:.1f} MB) exceeds maximum upload limit ({max_mb:.1f} MB)."
            )

        target_dir = Path(tempfile.mkdtemp(prefix="ingest_zip_", dir=self.temp_root)).resolve()

        try:
            extracted_size, total_files = self._extract_safely(file_obj, target_dir)
            logger.info(
                "Extracted %d files (%d bytes) for project '%s' to %s",
                total_files,
                extracted_size,
                name,
                target_dir,
            )

            metadata = {
                "archive_size_bytes": archive_size,
                "extracted_size_bytes": extracted_size,
                "file_count": total_files,
            }

            return ProjectSource(
                source_type="zip",
                name=name,
                extracted_path=target_dir,
                source_url=None,
                default_branch="main",
                commit_sha=None,
                metadata=metadata,
            )

        except Exception:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            raise
        finally:
            if hasattr(file_obj, "close"):
                try:
                    file_obj.close()
                except Exception:
                    pass

    def _prepare_source(
        self, source: Path | str | bytes | BinaryIO
    ) -> tuple[BinaryIO, int, str | None]:
        """Convert input source into a seekable BinaryIO object with size metadata."""
        if isinstance(source, (str, Path)):
            p = Path(source)
            if not p.is_file():
                raise ValueError(f"ZIP file not found at path: {source}")
            size = p.stat().st_size
            inferred_name = p.stem
            return open(p, "rb"), size, inferred_name

        if isinstance(source, bytes):
            size = len(source)
            return io.BytesIO(source), size, None

        if hasattr(source, "read") and hasattr(source, "seek"):
            source.seek(0, io.SEEK_END)
            size = source.tell()
            source.seek(0)
            inferred_name = getattr(source, "name", None)
            if inferred_name:
                inferred_name = Path(inferred_name).stem
            return source, size, inferred_name

        raise ValueError("Unsupported ZIP source format.")

    def _extract_safely(self, file_obj: BinaryIO, target_dir: Path) -> tuple[int, int]:
        """Verify zip integrity, prevent Zip Slip and zip bombs, and safely extract members."""
        try:
            zf = zipfile.ZipFile(file_obj)
        except zipfile.BadZipFile as e:
            raise ValueError("Uploaded file is not a valid ZIP archive.") from e

        members = zf.infolist()

        if len(members) > self.max_files_count:
            raise ValueError(
                f"Archive contains {len(members)} entries, exceeding the maximum allowed "
                f"limit of {self.max_files_count} files."
            )

        # 1. Pre-validation pass: check paths and cumulative uncompressed size
        cumulative_size = 0
        target_resolved = target_dir.resolve()

        for member in members:
            # Check for illegal path traversal (Zip-Slip)
            filename = member.filename
            if not filename or filename.startswith(("/", "\\")):
                raise ValueError(f"Dangerous absolute path detected in archive: {filename}")
            if ".." in Path(filename).parts:
                raise ValueError(f"Path traversal detected in archive entry: {filename}")

            # Resolve target destination path
            dest_path = (target_resolved / filename).resolve()
            if not dest_path.is_relative_to(target_resolved):
                raise ValueError(f"Path traversal target outside extraction directory: {filename}")

            # Reject dangerous symlinks or special devices
            mode = member.external_attr >> 16
            if mode:
                if (
                    stat.S_ISLNK(mode)
                    or stat.S_ISFIFO(mode)
                    or stat.S_ISCHR(mode)
                    or stat.S_ISBLK(mode)
                ):
                    raise ValueError(
                        f"Dangerous archive entry type detected (symlink/device): {filename}"
                    )

            cumulative_size += member.file_size
            if cumulative_size > self.max_extracted_size:
                c_mb = cumulative_size / (1024 * 1024)
                m_mb = self.max_extracted_size / (1024 * 1024)
                raise ValueError(
                    f"Uncompressed archive size ({c_mb:.1f} MB) exceeds limit ({m_mb:.1f} MB)."
                )

        # 2. Extraction pass with streaming byte limits
        actual_extracted = 0
        extracted_file_count = 0

        for member in members:
            dest_path = (target_resolved / member.filename).resolve()

            if member.is_dir():
                dest_path.mkdir(parents=True, exist_ok=True)
                continue

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with zf.open(member) as source_stream, open(dest_path, "wb") as dest_file:
                while chunk := source_stream.read(64 * 1024):
                    actual_extracted += len(chunk)
                    if actual_extracted > self.max_extracted_size:
                        raise ValueError(
                            "Extracted size exceeded limit during decompression (zip bomb)."
                        )
                    dest_file.write(chunk)

            # Strip executable permissions for security (set read/write only)
            try:
                os.chmod(dest_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
            except OSError:
                pass

            extracted_file_count += 1

        return actual_extracted, extracted_file_count
