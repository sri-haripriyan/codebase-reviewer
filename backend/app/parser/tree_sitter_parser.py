"""Tree-sitter based AST parser supporting Python, JavaScript, TypeScript, Java, C#, and Go."""

import tree_sitter_c_sharp as tscs
import tree_sitter_go as tsgo
import tree_sitter_java as tsjava
import tree_sitter_javascript as tsjs
import tree_sitter_python as tspython
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from backend.app.core.logging import get_logger
from backend.app.parser.base import BaseParser
from backend.app.parser.models import CodeElement, ImportStatement, ParsedFile

logger = get_logger(__name__)

# Cache of initialized Tree-sitter Language objects
_LANGUAGES: dict[str, Language] = {}


def _get_language(lang_key: str) -> Language | None:
    """Retrieve or initialize the Tree-sitter Language instance."""
    if lang_key in _LANGUAGES:
        return _LANGUAGES[lang_key]

    try:
        if lang_key == "python":
            lang = Language(tspython.language())
        elif lang_key in ("javascript", "jsx"):
            lang = Language(tsjs.language())
        elif lang_key == "typescript":
            lang = Language(tsts.language_typescript())
        elif lang_key == "tsx":
            lang = Language(tsts.language_tsx())
        elif lang_key == "java":
            lang = Language(tsjava.language())
        elif lang_key in ("csharp", "c#", "cs"):
            lang = Language(tscs.language())
        elif lang_key == "go":
            lang = Language(tsgo.language())
        else:
            return None
        _LANGUAGES[lang_key] = lang
        return lang
    except Exception as e:
        logger.warning("Failed to load Tree-sitter grammar for '%s': %s", lang_key, e)
        return None


class TreeSitterParser(BaseParser):
    """Parses source code into a language-independent ParsedFile representation
    using Tree-sitter.
    """

    def __init__(self, language: str) -> None:
        self.language = language.lower()
        self._ts_language = _get_language(self.language)
        if not self._ts_language:
            raise ValueError(f"Unsupported Tree-sitter language: {language}")
        self._parser = Parser(self._ts_language)

    def parse(self, code: str, file_path: str = "") -> ParsedFile:
        """Parse source code string into structured elements and import statements."""
        code_bytes = code.encode("utf-8", errors="replace")
        try:
            tree = self._parser.parse(code_bytes)
        except Exception as e:
            return ParsedFile(
                file_path=file_path,
                language=self.language,
                errors=[f"Tree-sitter parse crash: {e}"],
                raw_code=code,
            )

        root = tree.root_node
        errors: list[str] = []
        if root.has_error:
            errors.append(f"Syntax error detected in {file_path or 'input'}")

        imports: list[ImportStatement] = []
        elements: list[CodeElement] = []

        # Extract file-level docstring/comments
        file_docstring = self._extract_file_docstring(root, code_bytes)

        # Walk AST
        self._walk_node(root, code_bytes, elements, imports, parent_name=None)

        total_lines = len(code.splitlines())
        return ParsedFile(
            file_path=file_path,
            language=self.language,
            imports=imports,
            elements=elements,
            docstring=file_docstring,
            errors=errors,
            raw_code=code,
            total_lines=total_lines,
        )

    def _walk_node(
        self,
        node: Node,
        code_bytes: bytes,
        elements: list[CodeElement],
        imports: list[ImportStatement],
        parent_name: str | None = None,
    ) -> None:
        """Recursively process AST nodes and extract structured code symbols."""
        for child in node.children:
            ntype = child.type

            # Unwrap namespaces and declaration lists (C#)
            if ntype in (
                "namespace_declaration",
                "file_scoped_namespace_declaration",
                "declaration_list",
            ):
                self._walk_node(child, code_bytes, elements, imports, parent_name)
                continue

            # Unwrap export statements (TypeScript/JavaScript)
            if ntype == "export_statement":
                self._walk_node(child, code_bytes, elements, imports, parent_name)
                continue

            # Unwrap decorated definitions (Python)
            if ntype == "decorated_definition":
                self._handle_decorated_definition(child, code_bytes, elements, parent_name)
                continue

            # Imports
            if self._is_import_node(ntype):
                imp = self._parse_import(child, code_bytes)
                if imp:
                    imports.append(imp)
                continue

            # Classes and interfaces
            if self._is_class_or_interface(ntype):
                elem = self._parse_class_or_interface(child, code_bytes, parent_name)
                if elem:
                    elements.append(elem)
                continue

            # Functions and methods
            if self._is_function_or_method(ntype):
                elem = self._parse_function_or_method(child, code_bytes, parent_name)
                if elem:
                    elements.append(elem)
                continue

            # Go type declarations (e.g. type User struct {...})
            if ntype == "type_declaration" and self.language == "go":
                elem = self._parse_go_type(child, code_bytes)
                if elem:
                    elements.append(elem)
                continue

            # Arrow function assigned to a const / variable (JS/TS)
            if ntype in ("lexical_declaration", "variable_declaration") and self.language in (
                "javascript",
                "typescript",
                "jsx",
                "tsx",
            ):
                arrow_elem = self._parse_arrow_function(child, code_bytes, parent_name)
                if arrow_elem:
                    elements.append(arrow_elem)
                    continue

    def _is_import_node(self, ntype: str) -> bool:
        """Check if node represents an import statement."""
        return ntype in (
            "import_statement",
            "import_from_statement",
            "import_declaration",
            "using_directive",
        )

    def _is_class_or_interface(self, ntype: str) -> bool:
        """Check if node represents a class, interface, struct, or type alias."""
        return ntype in (
            "class_definition",  # Python
            "class_declaration",  # JS/TS/Java/C#
            "interface_declaration",  # TS/Java/C#
            "struct_declaration",  # C#
            "record_declaration",  # Java/C#
            "enum_declaration",  # Java/C#/TS
            "type_alias_declaration",  # TS
        )

    def _is_function_or_method(self, ntype: str) -> bool:
        """Check if node represents a function, method, or constructor."""
        return ntype in (
            "function_definition",  # Python
            "function_declaration",  # JS/TS/Go
            "method_definition",  # JS/TS
            "method_declaration",  # Java/C#/Go
            "constructor_declaration",  # Java/C#
        )

    def _parse_import(self, node: Node, code_bytes: bytes) -> ImportStatement | None:
        """Extract import information from node."""
        raw = self._node_text(node, code_bytes).strip()
        line = node.start_point[0] + 1
        return ImportStatement(module=raw, names=[], raw_statement=raw, line_number=line)

    def _parse_class_or_interface(
        self,
        node: Node,
        code_bytes: bytes,
        parent_name: str | None = None,
    ) -> CodeElement | None:
        """Extract class, interface, or struct details and child methods."""
        name_node = node.child_by_field_name("name")
        name = self._node_text(name_node, code_bytes) if name_node else "AnonymousClass"

        element_type = "class"
        if "interface" in node.type:
            element_type = "interface"
        elif "struct" in node.type:
            element_type = "struct"
        elif "type_alias" in node.type:
            element_type = "type_alias"

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        content = self._node_text(node, code_bytes)
        docstring = self._extract_docstring(node, code_bytes)

        children: list[CodeElement] = []
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if self._is_function_or_method(child.type):
                    method_elem = self._parse_function_or_method(
                        child, code_bytes, parent_name=name
                    )
                    if method_elem:
                        children.append(method_elem)

        return CodeElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
            parent_name=parent_name,
            docstring=docstring,
            content=content,
            children=children,
        )

    def _parse_function_or_method(
        self,
        node: Node,
        code_bytes: bytes,
        parent_name: str | None = None,
    ) -> CodeElement | None:
        """Extract function, method, or constructor details."""
        name_node = node.child_by_field_name("name")
        name = self._node_text(name_node, code_bytes) if name_node else "anonymous"

        # Go method receiver extraction
        if self.language == "go" and node.type == "method_declaration":
            receiver_node = node.child_by_field_name("receiver")
            if receiver_node:
                raw_recv = self._node_text(receiver_node, code_bytes)
                parts = raw_recv.replace("(", "").replace(")", "").replace("*", "").split()
                parent_name = parts[-1] if parts else raw_recv

        element_type = (
            "method"
            if (parent_name or node.type in ("method_declaration", "method_definition"))
            else "function"
        )

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        content = self._node_text(node, code_bytes)
        docstring = self._extract_docstring(node, code_bytes)

        # Extract parameters
        parameters: list[str] = []
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for p in params_node.children:
                if p.type not in (",", "(", ")"):
                    p_text = self._node_text(p, code_bytes).strip()
                    if p_text:
                        parameters.append(p_text)

        # Extract return type
        return_type = None
        ret_node = node.child_by_field_name("return_type") or node.child_by_field_name("result")
        if ret_node:
            return_type = self._node_text(ret_node, code_bytes).strip()

        return CodeElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
            parent_name=parent_name,
            docstring=docstring,
            parameters=parameters,
            return_type=return_type,
            content=content,
        )

    def _parse_arrow_function(
        self,
        node: Node,
        code_bytes: bytes,
        parent_name: str | None = None,
    ) -> CodeElement | None:
        """Handle JavaScript/TypeScript variable declarator assigned to an arrow function."""
        for child in node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if value_node and value_node.type == "arrow_function":
                    name = self._node_text(name_node, code_bytes) if name_node else "anonymous"
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    content = self._node_text(node, code_bytes)
                    return CodeElement(
                        name=name,
                        element_type="function",
                        start_line=start_line,
                        end_line=end_line,
                        parent_name=parent_name,
                        content=content,
                    )
        return None

    def _parse_go_type(self, node: Node, code_bytes: bytes) -> CodeElement | None:
        """Extract Go type_declaration (struct or interface)."""
        for child in node.children:
            if child.type == "type_spec":
                name_node = child.child_by_field_name("name")
                type_node = child.child_by_field_name("type")
                name = self._node_text(name_node, code_bytes) if name_node else "AnonymousType"
                t_str = self._node_text(type_node, code_bytes) if type_node else ""
                elem_type = "interface" if "interface" in t_str else "struct"
                return CodeElement(
                    name=name,
                    element_type=elem_type,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    content=self._node_text(node, code_bytes),
                )
        return None

    def _handle_decorated_definition(
        self,
        node: Node,
        code_bytes: bytes,
        elements: list[CodeElement],
        parent_name: str | None = None,
    ) -> None:
        """Extract Python function/class definition enclosed in decorators."""
        def_node = node.child_by_field_name("definition")
        if not def_node:
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    def_node = child
                    break

        if def_node:
            if def_node.type == "function_definition":
                elem = self._parse_function_or_method(def_node, code_bytes, parent_name)
                if elem:
                    # Encompass decorator lines in content and start line
                    elem.start_line = node.start_point[0] + 1
                    elem.content = self._node_text(node, code_bytes)
                    elements.append(elem)
            elif def_node.type == "class_definition":
                elem = self._parse_class_or_interface(def_node, code_bytes, parent_name)
                if elem:
                    elem.start_line = node.start_point[0] + 1
                    elem.content = self._node_text(node, code_bytes)
                    elements.append(elem)

    def _extract_docstring(self, node: Node, code_bytes: bytes) -> str | None:
        """Extract docstring or preceding block comments for an AST element."""
        if self.language == "python":
            body = node.child_by_field_name("body")
            if body and body.children:
                first_stmt = body.children[0]
                if first_stmt.type == "expression_statement":
                    for child in first_stmt.children:
                        if child.type == "string":
                            text = self._node_text(child, code_bytes).strip("\"' \t\n")
                            return text
        return None

    def _extract_file_docstring(self, root: Node, code_bytes: bytes) -> str | None:
        """Extract file/module level docstring."""
        if self.language == "python" and root.children:
            first_child = root.children[0]
            if first_child.type == "expression_statement":
                for sub in first_child.children:
                    if sub.type == "string":
                        return self._node_text(sub, code_bytes).strip("\"' \t\n")
        return None

    def _node_text(self, node: Node | None, code_bytes: bytes) -> str:
        """Decode slice of source code corresponding to node bytes."""
        if not node:
            return ""
        return code_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
