"""Unit tests for AST and heuristic code parsing."""

from pathlib import Path

from backend.app.parser.factory import get_parser_for_language, parse_source_code
from backend.app.parser.fallback_parser import FallbackParser
from backend.app.parser.tree_sitter_parser import TreeSitterParser

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "sample_code"


def test_parser_factory_resolution():
    """Verify that factory resolves Tree-sitter for supported langs and fallback for others."""
    for lang in ["python", "javascript", "typescript", "java", "csharp", "go"]:
        parser = get_parser_for_language(lang)
        assert isinstance(parser, TreeSitterParser)
        assert parser.language in (lang, "csharp")

    fallback = get_parser_for_language("unknown_lang")
    assert isinstance(fallback, FallbackParser)


def test_parse_python_sample():
    """Verify Python AST parsing: classes, methods, functions, docstrings, imports."""
    sample_file = FIXTURES_DIR / "sample.py"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="python", file_path="sample.py")

    assert parsed.language == "python"
    assert parsed.total_lines > 50

    # Verify imports
    import_mods = [imp.module for imp in parsed.imports]
    assert any("os" in mod for mod in import_mods)
    assert any("sys" in mod for mod in import_mods)
    assert any("typing" in mod for mod in import_mods)

    # Verify class
    class_elem = next((e for e in parsed.elements if e.name == "DataProcessor"), None)
    assert class_elem is not None
    assert class_elem.element_type == "class"
    assert "Processes datasets" in (class_elem.docstring or "")
    assert len(class_elem.children) == 2
    method_names = [m.name for m in class_elem.children]
    assert "__init__" in method_names
    assert "process" in method_names

    # Verify top-level functions
    func_names = [e.name for e in parsed.elements if e.element_type == "function"]
    assert "calculate_metrics" in func_names
    assert "large_data_transformer" in func_names

    # Verify function docstring
    calc_func = next(e for e in parsed.elements if e.name == "calculate_metrics")
    assert "Calculate mean and variance" in (calc_func.docstring or "")


def test_parse_typescript_sample():
    """Verify TypeScript AST parsing: interfaces, classes, methods, functions, imports."""
    sample_file = FIXTURES_DIR / "sample.ts"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="typescript", file_path="sample.ts")

    assert parsed.language == "typescript"

    # Verify imports
    import_mods = [imp.module for imp in parsed.imports]
    assert any("./types" in mod for mod in import_mods)
    assert any("path" in mod for mod in import_mods)

    # Verify interface
    iface = next((e for e in parsed.elements if e.name == "UserProfile"), None)
    assert iface is not None
    assert iface.element_type == "interface"

    # Verify class and methods
    cls = next((e for e in parsed.elements if e.name == "UserService"), None)
    assert cls is not None
    assert cls.element_type == "class"
    method_names = [m.name for m in cls.children]
    assert "getUserById" in method_names

    # Verify standalone function
    fn = next((e for e in parsed.elements if e.name == "formatGreeting"), None)
    assert fn is not None
    assert fn.element_type == "function"


def test_parse_javascript_sample():
    """Verify JavaScript AST parsing: classes, functions, and requires."""
    sample_file = FIXTURES_DIR / "sample.js"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="javascript", file_path="sample.js")

    assert parsed.language == "javascript"

    # Verify class
    cls = next((e for e in parsed.elements if e.name == "FileManager"), None)
    assert cls is not None
    assert cls.element_type == "class"
    method_names = [m.name for m in cls.children]
    assert "readFile" in method_names

    # Verify function
    fn = next((e for e in parsed.elements if e.name == "calculateSum"), None)
    assert fn is not None
    assert fn.element_type == "function"


def test_parse_java_sample():
    """Verify Java AST parsing: classes, constructors, methods, and imports."""
    sample_file = FIXTURES_DIR / "Sample.java"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="java", file_path="Sample.java")

    assert parsed.language == "java"

    # Verify imports
    import_mods = [imp.module for imp in parsed.imports]
    assert any("java.util.List" in mod for mod in import_mods)

    # Verify class
    cls = next((e for e in parsed.elements if e.name == "OrderService"), None)
    assert cls is not None
    assert cls.element_type == "class"
    method_names = [m.name for m in cls.children]
    assert "addOrder" in method_names
    assert "getOrderCount" in method_names


def test_parse_csharp_sample():
    """Verify C# AST parsing: classes, methods, and usings."""
    sample_file = FIXTURES_DIR / "Sample.cs"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="csharp", file_path="Sample.cs")

    assert parsed.language == "csharp"

    # Verify imports (usings)
    import_mods = [imp.module for imp in parsed.imports]
    assert any("System" in mod for mod in import_mods)

    # Verify class
    cls = next((e for e in parsed.elements if e.name == "CustomerService"), None)
    assert cls is not None
    assert cls.element_type == "class"
    method_names = [m.name for m in cls.children]
    assert "RegisterCustomer" in method_names
    assert "CustomerCount" in method_names


def test_parse_go_sample():
    """Verify Go AST parsing: structs, receiver methods, functions, and package imports."""
    sample_file = FIXTURES_DIR / "sample.go"
    code = sample_file.read_text(encoding="utf-8")
    parsed = parse_source_code(code, language="go", file_path="sample.go")

    assert parsed.language == "go"

    # Verify struct
    struct_elem = next((e for e in parsed.elements if e.name == "Repository"), None)
    assert struct_elem is not None
    assert struct_elem.element_type == "struct"

    # Verify receiver method
    method_elem = next((e for e in parsed.elements if e.name == "FullName"), None)
    assert method_elem is not None
    assert method_elem.element_type == "method"
    assert method_elem.parent_name == "Repository"

    # Verify function
    fn = next((e for e in parsed.elements if e.name == "CleanURL"), None)
    assert fn is not None
    assert fn.element_type == "function"


def test_parse_malformed_code_resilience():
    """Verify parser does not crash on malformed syntax and returns best-effort result."""
    sample_file = FIXTURES_DIR / "malformed.py"
    code = sample_file.read_text(encoding="utf-8")

    # Should not raise exception
    parsed = parse_source_code(code, language="python", file_path="malformed.py")
    assert parsed is not None
    assert parsed.file_path == "malformed.py"


def test_parse_unsupported_language_fallback():
    """Verify unsupported language falls back gracefully to FallbackParser without error."""
    sample_file = FIXTURES_DIR / "sample.md"
    code = sample_file.read_text(encoding="utf-8")

    parsed = parse_source_code(code, language="markdown", file_path="sample.md")
    assert parsed is not None
    assert parsed.language == "markdown"
    assert parsed.metadata.get("parser") == "fallback"
