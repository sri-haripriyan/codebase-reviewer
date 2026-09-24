"""Unit tests for semantic and generic code chunking."""

from pathlib import Path

from backend.app.chunker.generic_chunker import GenericChunker
from backend.app.chunker.pipeline import ChunkingService
from backend.app.chunker.semantic_chunker import SemanticChunker
from backend.app.parser.factory import parse_source_code

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_code"


def test_generic_chunker_small_code():
    """Verify that generic chunker returns a single chunk for code under max_lines."""
    chunker = GenericChunker(max_lines=50)
    code = "line 1\nline 2\nline 3\n"
    chunks = chunker.chunk(code, file_path="small.txt", language="text")

    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3
    assert chunks[0].chunk_type == "generic"


def test_generic_chunker_sliding_window():
    """Verify sliding window with line overlap for code exceeding max_lines."""
    chunker = GenericChunker(max_lines=30, overlap_lines=5)
    lines = [f"line {i}\n" for i in range(1, 75)]
    code = "".join(lines)

    chunks = chunker.chunk(code, file_path="long.txt", language="text")
    assert len(chunks) > 1

    # First chunk covers lines 1 to 30
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 30
    assert chunks[0].metadata["part_index"] == 1

    # Second chunk covers lines 26 to 55 (due to 5 lines overlap)
    assert chunks[1].start_line == 26
    assert chunks[1].end_line == 55
    assert chunks[1].metadata["part_index"] == 2


def test_semantic_chunker_preserves_whole_functions():
    """Verify that normal-sized functions are kept whole without splitting."""
    sample_file = FIXTURES_DIR / "sample.py"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="python", file_path="sample.py")

    chunker = SemanticChunker(max_lines=120)
    chunks = chunker.chunk_file(parsed, code)

    # Find the chunk for calculate_metrics
    calc_chunk = next((c for c in chunks if c.symbol_name == "calculate_metrics"), None)
    assert calc_chunk is not None
    assert calc_chunk.chunk_type == "function"
    assert "def calculate_metrics" in calc_chunk.content
    assert "return {" in calc_chunk.content
    # Function was not split
    assert not calc_chunk.metadata.get("is_split")


def test_semantic_chunker_module_header():
    """Verify that module header capturing imports is generated."""
    sample_file = FIXTURES_DIR / "sample.py"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="python", file_path="sample.py")

    chunker = SemanticChunker(max_lines=120)
    chunks = chunker.chunk_file(parsed, code)

    header = next((c for c in chunks if c.chunk_type == "module_header"), None)
    assert header is not None
    assert "import os" in header.content
    assert header.start_line == 1


def test_semantic_chunker_controlled_splitting():
    """Verify that oversized functions undergo controlled splitting with context headers."""
    sample_file = FIXTURES_DIR / "sample.py"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="python", file_path="sample.py")

    # Use max_lines=60 to force large_data_transformer (>130 lines) to split
    chunker = SemanticChunker(max_lines=60, overlap_lines=10)
    chunks = chunker.chunk_file(parsed, code)

    split_chunks = [c for c in chunks if c.symbol_name == "large_data_transformer"]
    assert len(split_chunks) >= 2

    # Part 1 should have start_line matching the function start
    assert split_chunks[0].metadata["part_index"] == 1
    assert split_chunks[0].metadata["is_split"] is True

    # Part 2 should contain context header
    assert split_chunks[1].metadata["part_index"] == 2
    assert "# [Context: large_data_transformer" in split_chunks[1].content


def test_semantic_chunker_class_method_parent_tracking():
    """Verify methods inside classes retain parent_name."""
    sample_file = FIXTURES_DIR / "sample.ts"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="typescript", file_path="sample.ts")

    chunker = SemanticChunker(max_lines=100)
    chunks = chunker.chunk_file(parsed, code)

    # Check for getUserById method or UserService class
    method_chunk = next((c for c in chunks if c.symbol_name == "getUserById"), None)
    if method_chunk:
        assert method_chunk.parent_name == "UserService"
    else:
        # If class fits in max_lines, whole class is emitted
        class_chunk = next((c for c in chunks if c.symbol_name == "UserService"), None)
        assert class_chunk is not None
        assert "getUserById" in class_chunk.content


def test_chunking_service_pipeline():
    """Verify end-to-end ChunkingService across languages and fallbacks."""
    service = ChunkingService()

    # 1. Python
    py_code = FIXTURES_DIR.joinpath("sample.py").read_text(encoding="utf-8")
    py_chunks = service.process_code(
        py_code,
        language="python",
        file_path="sample.py",
        extra_metadata={"project_id": "test-p1"},
    )
    assert len(py_chunks) > 0
    assert all(c.metadata.get("project_id") == "test-p1" for c in py_chunks)

    # 2. Go
    go_code = FIXTURES_DIR.joinpath("sample.go").read_text(encoding="utf-8")
    go_chunks = service.process_code(go_code, language="go", file_path="sample.go")
    assert len(go_chunks) > 0

    # 3. Fallback on Markdown
    md_code = FIXTURES_DIR.joinpath("sample.md").read_text(encoding="utf-8")
    md_chunks = service.process_code(md_code, language="markdown", file_path="sample.md")
    assert len(md_chunks) > 0

    # 4. Empty code
    assert service.process_code("", language="python") == []
    assert service.process_code("   \n  ", language="python") == []
