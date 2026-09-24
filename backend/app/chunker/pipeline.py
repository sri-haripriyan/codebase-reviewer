"""Chunking service orchestrating parsing and chunking across scanned files."""

from pathlib import Path
from typing import Any

from backend.app.chunker.generic_chunker import GenericChunker
from backend.app.chunker.models import CodeChunk
from backend.app.chunker.semantic_chunker import SemanticChunker
from backend.app.core.config import settings
from backend.app.core.logging import get_logger
from backend.app.parser.factory import parse_source_code

logger = get_logger(__name__)


class ChunkingService:
    """High-level service providing unified parsing and chunking for repository files."""

    def __init__(
        self,
        max_lines: int | None = None,
        min_lines: int | None = None,
        overlap_lines: int | None = None,
        max_chars: int | None = None,
    ) -> None:
        self.max_lines = max_lines or settings.CHUNK_MAX_LINES
        self.min_lines = min_lines or settings.CHUNK_MIN_LINES
        self.overlap_lines = overlap_lines or settings.CHUNK_OVERLAP_LINES
        self.max_chars = max_chars or settings.CHUNK_MAX_CHARS

        self.semantic_chunker = SemanticChunker(
            max_lines=self.max_lines,
            min_lines=self.min_lines,
            overlap_lines=self.overlap_lines,
            max_chars=self.max_chars,
        )
        self.generic_chunker = GenericChunker(
            max_lines=self.max_lines,
            overlap_lines=self.overlap_lines,
        )

    def process_code(
        self,
        code: str,
        language: str,
        file_path: str = "",
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[CodeChunk]:
        """Parse and chunk source code string safely without raising exceptions."""
        if not code or not code.strip():
            return []

        extra_meta = extra_metadata or {}

        try:
            # 1. Parse code into language-independent AST representation
            parsed = parse_source_code(code=code, language=language, file_path=file_path)

            # 2. Chunk code using AST structure
            chunks = self.semantic_chunker.chunk_file(parsed, code)

            # 3. Augment chunks with any extra metadata (e.g. project_id, file_id)
            if extra_meta:
                for c in chunks:
                    c.metadata.update(extra_meta)

            return chunks

        except Exception as e:
            logger.warning(
                "Semantic chunking failed for %s (%s). Falling back to generic chunker: %s",
                file_path,
                language,
                e,
            )
            try:
                chunks = self.generic_chunker.chunk(
                    code=code,
                    file_path=file_path,
                    language=language,
                    metadata={"chunk_strategy": "emergency_generic_fallback"},
                )
                if extra_meta:
                    for c in chunks:
                        c.metadata.update(extra_meta)
                return chunks
            except Exception as inner_err:
                logger.error(
                    "Emergency generic chunker also failed for %s: %s",
                    file_path,
                    inner_err,
                )
                return []

    def process_file_on_disk(
        self,
        disk_path: Path,
        relative_path: str,
        language: str,
        extra_metadata: dict[str, Any] | None = None,
    ) -> list[CodeChunk]:
        """Read a file from disk and generate code chunks."""
        try:
            code = disk_path.read_text(encoding="utf-8", errors="replace")
            return self.process_code(
                code=code,
                language=language,
                file_path=relative_path,
                extra_metadata=extra_metadata,
            )
        except Exception as e:
            logger.warning("Could not read file %s for chunking: %s", disk_path, e)
            return []
