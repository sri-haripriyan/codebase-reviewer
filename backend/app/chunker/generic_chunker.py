"""Generic sliding-window chunker for unsupported languages or fallback situations."""

from typing import Any

from backend.app.chunker.models import CodeChunk
from backend.app.core.config import settings


class GenericChunker:
    """Chunks arbitrary code or text using a sliding window with line overlap."""

    def __init__(
        self,
        max_lines: int | None = None,
        overlap_lines: int | None = None,
    ) -> None:
        self.max_lines = max_lines or settings.CHUNK_MAX_LINES
        self.overlap_lines = overlap_lines or settings.CHUNK_OVERLAP_LINES

    def chunk(
        self,
        code: str,
        file_path: str = "",
        language: str = "generic",
        metadata: dict[str, Any] | None = None,
    ) -> list[CodeChunk]:
        """Split code into overlapping line-based chunks."""
        base_meta = dict(metadata or {})
        lines = code.splitlines(keepends=True)
        total_lines = len(lines)

        if total_lines == 0:
            return []

        # If file is small enough, return as a single chunk
        if total_lines <= self.max_lines:
            return [
                CodeChunk(
                    file_path=file_path,
                    language=language,
                    content=code,
                    start_line=1,
                    end_line=total_lines,
                    chunk_type="generic",
                    symbol_name=None,
                    parent_name=None,
                    metadata={**base_meta, "chunk_strategy": "generic_full"},
                )
            ]

        chunks: list[CodeChunk] = []
        step = max(1, self.max_lines - self.overlap_lines)
        start_idx = 0
        part_idx = 1

        while start_idx < total_lines:
            end_idx = min(start_idx + self.max_lines, total_lines)
            chunk_content = "".join(lines[start_idx:end_idx])

            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    language=language,
                    content=chunk_content,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    chunk_type="generic",
                    symbol_name=None,
                    parent_name=None,
                    metadata={
                        **base_meta,
                        "chunk_strategy": "generic_sliding_window",
                        "part_index": part_idx,
                    },
                )
            )

            if end_idx >= total_lines:
                break

            start_idx += step
            part_idx += 1

        # Populate total_parts in metadata
        total_parts = len(chunks)
        for c in chunks:
            c.metadata["total_parts"] = total_parts

        return chunks
