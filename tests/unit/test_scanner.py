"""Unit tests for the codebase file scanner, ignore rules, and language detection."""

import tempfile
from pathlib import Path

import pytest

from backend.app.ingestion.scanner import (
    CodebaseScanner,
    calculate_file_hash,
    detect_language,
    is_binary_file,
)


@pytest.fixture
def sample_workspace():
    """Create a temporary directory structure mimicking a real software project."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_scan_"))
    try:
        # 1. Valid source files
        (temp_dir / "src").mkdir()
        (temp_dir / "src" / "main.py").write_text(
            "def run():\n    print('hello')\n", encoding="utf-8"
        )
        (temp_dir / "src" / "app.ts").write_text("const msg: string = 'hi';\n", encoding="utf-8")
        (temp_dir / "README.md").write_text("# Test Repo\nDocumentation\n", encoding="utf-8")
        (temp_dir / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")

        # 2. Duplicate file with identical content as main.py
        (temp_dir / "src" / "copy_main.py").write_text(
            "def run():\n    print('hello')\n", encoding="utf-8"
        )

        # 3. Ignored directories
        (temp_dir / ".git").mkdir()
        (temp_dir / ".git" / "config").write_text("git config content", encoding="utf-8")

        (temp_dir / "node_modules" / "pkg").mkdir(parents=True)
        (temp_dir / "node_modules" / "pkg" / "index.js").write_text(
            "module.exports = {};", encoding="utf-8"
        )

        (temp_dir / ".venv" / "lib").mkdir(parents=True)
        (temp_dir / ".venv" / "lib" / "pip.py").write_text("pip internal", encoding="utf-8")

        (temp_dir / "__pycache__").mkdir()
        (temp_dir / "__pycache__" / "main.cpython-312.pyc").write_bytes(b"\x00\x01\x02\x03")

        (temp_dir / "dist").mkdir()
        (temp_dir / "dist" / "bundle.js").write_text("bundled code", encoding="utf-8")

        # 4. Binary file with null bytes
        (temp_dir / "src" / "data.bin").write_bytes(b"header\x00\x01\x02\x03data")

        # 5. Ignored image extension
        (temp_dir / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n")

        yield temp_dir
    finally:
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)


def test_ignored_directories_and_extensions(sample_workspace: Path):
    """Verify that scanner ignores .git, node_modules, .venv, dist, and binary files."""
    scanner = CodebaseScanner()
    scanned_files, duplicates = scanner.scan(sample_workspace)

    discovered_paths = {f.relative_path for f in scanned_files}

    # Should contain valid source files
    assert "src/main.py" in discovered_paths
    assert "src/app.ts" in discovered_paths
    assert "README.md" in discovered_paths
    assert "Dockerfile" in discovered_paths
    assert "src/copy_main.py" in discovered_paths

    # Should NOT contain ignored directory files
    for p in discovered_paths:
        assert not p.startswith(".git")
        assert not p.startswith("node_modules")
        assert not p.startswith(".venv")
        assert not p.startswith("__pycache__")
        assert not p.startswith("dist")
        assert not p.endswith(".png")
        assert not p.endswith(".bin")


def test_duplicate_file_detection(sample_workspace: Path):
    """Verify that duplicate files sharing identical SHA-256 hashes are captured."""
    scanner = CodebaseScanner()
    _, duplicates = scanner.scan(sample_workspace)

    assert len(duplicates) == 1
    hash_key = list(duplicates.keys())[0]
    duplicate_paths = set(duplicates[hash_key])

    assert duplicate_paths == {"src/main.py", "src/copy_main.py"}


def test_language_detection():
    """Verify language detection across standard extensions and well-known filenames."""
    assert detect_language(Path("main.py")) == "python"
    assert detect_language(Path("app.ts")) == "typescript"
    assert detect_language(Path("component.jsx")) == "javascript"
    assert detect_language(Path("styles.css")) == "css"
    assert detect_language(Path("schema.sql")) == "sql"
    assert detect_language(Path("Dockerfile")) == "dockerfile"
    assert detect_language(Path("Makefile")) == "makefile"
    assert detect_language(Path("unknown.xyz")) == "unknown"


def test_binary_file_check(tmp_path: Path):
    """Verify null-byte detection distinguishing text from binary files."""
    text_file = tmp_path / "text.txt"
    text_file.write_text("Hello, world! Normal text file.", encoding="utf-8")
    assert is_binary_file(text_file) is False

    binary_file = tmp_path / "binary.raw"
    binary_file.write_bytes(b"Some text\x00with null byte")
    assert is_binary_file(binary_file) is True


def test_file_hash_calculation(tmp_path: Path):
    """Verify consistent SHA-256 hash calculation."""
    f = tmp_path / "hello.txt"
    f.write_text("hello", encoding="utf-8")
    expected_hash = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert calculate_file_hash(f) == expected_hash
