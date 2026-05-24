from __future__ import annotations

import ast
import hashlib
import math
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from backend.models import (
    ArchitectureMap,
    ChatResponse,
    CodeSymbol,
    RepositoryCodeIntelligence,
    RepositoryScan,
    RouteEndpoint,
    SemanticMemoryItem,
    AuthFlow,
    StateFlow,
)


SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
JS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
PYTHON_EXTENSIONS = {".py"}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
STOP_WORDS = {
    "a",
    "about",
    "after",
    "all",
    "an",
    "and",
    "api",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "code",
    "does",
    "file",
    "for",
    "from",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "repo",
    "repository",
    "should",
    "the",
    "this",
    "to",
    "what",
    "where",
    "with",
    "works",
}


@dataclass
class ImportReference:
    specifier: str
    imported_names: list[str] = field(default_factory=list)
    kind: str = "import"


@dataclass
class FileIntelligence:
    file: str
    language: str
    imports: list[ImportReference] = field(default_factory=list)
    symbols: list[CodeSymbol] = field(default_factory=list)
    routes: list[RouteEndpoint] = field(default_factory=list)
    env: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    preview: str = ""

    def imports_as_terms(self) -> list[str]:
        return [import_ref.specifier for import_ref in self.imports] + [
            name for import_ref in self.imports for name in import_ref.imported_names
        ]


class RepositoryCodeIntelligenceBuilder:
    def analyze(self, scan: RepositoryScan, architecture: ArchitectureMap | None = None) -> RepositoryCodeIntelligence:
        repo_path = Path(scan.path)
        source_files = [file for file in scan.files if PurePosixPath(file).suffix.lower() in SOURCE_EXTENSIONS]
        parsed = self._parse_files(repo_path, source_files)

        symbols = [symbol for file_info in parsed.values() for symbol in file_info.symbols]
        routes = [route for file_info in parsed.values() for route in file_info.routes]
        self._connect_symbol_graph(symbols, parsed)

        auth = self._auth_flow(scan, parsed, symbols, routes)
        state = self._state_flow(scan, symbols, parsed)
        runtime = self._runtime_map(scan, architecture, symbols, routes, parsed)
        deployment = self._deployment_map(scan)
        memory = self._semantic_memory(scan, architecture, symbols, routes, auth, state, runtime, deployment, parsed)
        confidence = self._confidence(symbols, routes, auth, state, parsed)

        return RepositoryCodeIntelligence(
            symbols=symbols[:2500],
            symbol_graph=self._symbol_graph(symbols, routes, parsed),
            routes=routes[:500],
            auth=auth,
            state=state,
            runtime=runtime,
            deployment=deployment,
            semantic_memory=memory[:1200],
            retrieval_stats={
                "source_files_analyzed": len(source_files),
                "symbols_indexed": len(symbols),
                "routes_indexed": len(routes),
                "memory_items": len(memory),
                "engine": "codesherpa-symbolic-rag-v1",
                "embedding_mode": "local lexical vectors",
            },
            confidence=confidence,
        )

    def _parse_files(self, repo_path: Path, files: list[str]) -> dict[str, FileIntelligence]:
        if not files:
            return {}

        def parse_one(file: str) -> tuple[str, FileIntelligence]:
            return file, self._parse_file(repo_path, file)

        with ThreadPoolExecutor(max_workers=min(12, max(1, len(files)))) as pool:
            return dict(pool.map(parse_one, files))

    def _parse_file(self, repo_path: Path, file: str) -> FileIntelligence:
        path = repo_path / file
        suffix = PurePosixPath(file).suffix.lower()
        language = self._language_for_suffix(suffix)
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return FileIntelligence(file=file, language=language)

        preview = self._compact_preview(text)
        if suffix in PYTHON_EXTENSIONS:
            return self._parse_python(file, text, preview)
        if suffix in JS_EXTENSIONS:
            return self._parse_js(file, text, preview)
        return FileIntelligence(file=file, language=language, preview=preview)

    @staticmethod
    def _language_for_suffix(suffix: str) -> str:
        return {
            ".py": "Python",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".mjs": "JavaScript",
            ".cjs": "JavaScript",
        }.get(suffix, "Source")

    def _parse_python(self, file: str, text: str, preview: str) -> FileIntelligence:
        info = FileIntelligence(file=file, language="Python", preview=preview)
        try:
            tree = ast.parse(text)
        except SyntaxError:
            info.signals.extend(self._text_signals(file, text))
            return info

        info.imports.extend(self._python_imports(tree))
        info.env.extend(self._python_env_usage(tree))
        info.calls.extend(self._python_calls(tree))
        info.signals.extend(self._text_signals(file, text))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = [self._safe_unparse(decorator) for decorator in node.decorator_list]
                calls = self._python_calls_from_body(node)
                env = self._python_env_usage(node)
                symbol_type = self._classify_python_symbol(file, node.name, decorators, calls, is_class=False)
                symbol = CodeSymbol(
                    id=self._symbol_id(file, node.name, node.lineno),
                    name=node.name,
                    type=symbol_type,
                    file=file,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", None),
                    language="Python",
                    runtime_role=self._runtime_role(file, symbol_type, decorators),
                    signature=self._python_signature(node),
                    imports=self._format_imports(info.imports),
                    calls=calls[:80],
                    decorators=[decorator for decorator in decorators if decorator],
                    metadata={
                        "async": isinstance(node, ast.AsyncFunctionDef),
                        "environment": env,
                    },
                )
                info.symbols.append(symbol)
                info.routes.extend(self._python_routes(file, node, decorators, calls))
            elif isinstance(node, ast.ClassDef):
                decorators = [self._safe_unparse(decorator) for decorator in node.decorator_list]
                bases = [self._safe_unparse(base) for base in node.bases]
                calls = self._python_calls_from_body(node)
                symbol_type = self._classify_python_symbol(file, node.name, decorators + bases, calls, is_class=True)
                symbol = CodeSymbol(
                    id=self._symbol_id(file, node.name, node.lineno),
                    name=node.name,
                    type=symbol_type,
                    file=file,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", None),
                    language="Python",
                    runtime_role=self._runtime_role(file, symbol_type, decorators),
                    signature=f"class {node.name}({', '.join(base for base in bases if base)})",
                    imports=self._format_imports(info.imports),
                    calls=calls[:80],
                    decorators=[decorator for decorator in decorators if decorator],
                    metadata={"bases": [base for base in bases if base]},
                )
                info.symbols.append(symbol)

        return info

    @staticmethod
    def _python_imports(tree: ast.AST) -> list[ImportReference]:
        imports: list[ImportReference] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportReference(alias.name, [alias.asname or alias.name.split(".")[0]], "python import"))
            elif isinstance(node, ast.ImportFrom):
                names = [alias.asname or alias.name for alias in node.names if alias.name != "*"]
                module = f"{'.' * node.level}{node.module or ''}"
                imports.append(ImportReference(module, names, "python import"))
        return imports

    @staticmethod
    def _python_calls(tree: ast.AST) -> list[str]:
        calls: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = RepositoryCodeIntelligenceBuilder._python_call_name(node.func)
                if name:
                    calls.append(name)
        return list(dict.fromkeys(calls))

    @staticmethod
    def _python_calls_from_body(node: ast.AST) -> list[str]:
        calls: list[str] = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = RepositoryCodeIntelligenceBuilder._python_call_name(child.func)
                if name:
                    calls.append(name)
        return list(dict.fromkeys(calls))

    @staticmethod
    def _python_call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = RepositoryCodeIntelligenceBuilder._python_call_name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        if isinstance(node, ast.Subscript):
            return RepositoryCodeIntelligenceBuilder._python_call_name(node.value)
        return ""

    @staticmethod
    def _python_env_usage(tree: ast.AST) -> list[str]:
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and RepositoryCodeIntelligenceBuilder._python_call_name(node.func) in {"os.getenv", "environ.get", "os.environ.get"}:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    names.append(node.args[0].value)
            elif isinstance(node, ast.Subscript):
                target = RepositoryCodeIntelligenceBuilder._python_call_name(node.value)
                if target in {"os.environ", "environ"}:
                    value = node.slice
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        names.append(value.value)
        return list(dict.fromkeys(names))

    def _python_routes(self, file: str, node: ast.FunctionDef | ast.AsyncFunctionDef, decorators: list[str], calls: list[str]) -> list[RouteEndpoint]:
        routes: list[RouteEndpoint] = []
        dependencies = [
            call
            for call in calls
            if call.endswith("Depends") or call == "Depends" or "Depends" in call or "Security" in call
        ]
        for decorator in decorators:
            parsed = self._parse_python_route_decorator(decorator)
            if not parsed:
                continue
            methods, path = parsed
            middleware = self._middleware_from_text(decorator + " " + " ".join(dependencies))
            auth_required = self._auth_required_from_terms(middleware + dependencies + [decorator, node.name])
            for method in methods:
                route_id = self._route_id(method, path, file, node.lineno)
                routes.append(
                    RouteEndpoint(
                        id=route_id,
                        method=method,
                        path=path,
                        file=file,
                        line=node.lineno,
                        framework="FastAPI",
                        controller=node.name,
                        middleware=middleware,
                        auth_required=auth_required,
                        dependencies=dependencies,
                        symbols=[self._symbol_id(file, node.name, node.lineno)],
                        metadata={"decorator": decorator},
                    )
                )
        return routes

    @staticmethod
    def _parse_python_route_decorator(decorator: str) -> tuple[list[str], str] | None:
        match = re.search(
            r"(?:router|app|api|blueprint)\.(get|post|put|patch|delete|options|head|api_route|route)\(\s*['\"]([^'\"]+)['\"]",
            decorator,
        )
        if not match:
            return None
        raw_method = match.group(1).upper()
        path = match.group(2)
        if raw_method in {"API_ROUTE", "ROUTE"}:
            methods_match = re.search(r"methods\s*=\s*\[([^\]]+)\]", decorator)
            if methods_match:
                methods = [item.upper() for item in re.findall(r"['\"]([A-Za-z]+)['\"]", methods_match.group(1))]
            else:
                methods = ["GET"]
        else:
            methods = [raw_method]
        return [method for method in methods if method in HTTP_METHODS], path

    def _parse_js(self, file: str, text: str, preview: str) -> FileIntelligence:
        info = FileIntelligence(file=file, language=self._language_for_suffix(PurePosixPath(file).suffix.lower()), preview=preview)
        info.imports.extend(self._js_imports(text))
        info.env.extend(self._js_env_usage(text))
        info.calls.extend(self._js_calls(text))
        info.signals.extend(self._text_signals(file, text))

        for match in re.finditer(r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(([^)]*)\)", text):
            name = match.group(1)
            line = self._line_number(text, match.start())
            type_ = self._classify_js_symbol(file, name, text[max(0, match.start() - 160): match.end() + 220], is_class=False)
            info.symbols.append(
                CodeSymbol(
                    id=self._symbol_id(file, name, line),
                    name=name,
                    type=type_,
                    file=file,
                    line=line,
                    language=info.language,
                    runtime_role=self._runtime_role(file, type_, []),
                    signature=f"function {name}({self._clean_params(match.group(2))})",
                    imports=self._format_imports(info.imports),
                    calls=self._js_calls(text[match.end(): match.end() + 2000])[:80],
                    metadata={"exported": match.group(0).lstrip().startswith("export")},
                )
            )

        for match in re.finditer(r"(?:export\s+)?class\s+([A-Za-z_$][\w$]*)\b(?:\s+extends\s+([A-Za-z_$][\w$.\-]*))?", text):
            name = match.group(1)
            line = self._line_number(text, match.start())
            type_ = self._classify_js_symbol(file, name, text[max(0, match.start() - 160): match.end() + 260], is_class=True)
            info.symbols.append(
                CodeSymbol(
                    id=self._symbol_id(file, name, line),
                    name=name,
                    type=type_,
                    file=file,
                    line=line,
                    language=info.language,
                    runtime_role=self._runtime_role(file, type_, []),
                    signature=f"class {name}",
                    imports=self._format_imports(info.imports),
                    calls=self._js_calls(text[match.end(): match.end() + 2400])[:80],
                    metadata={"extends": match.group(2), "exported": match.group(0).lstrip().startswith("export")},
                )
            )

        for match in re.finditer(
            r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
            text,
        ):
            name = match.group(1)
            line = self._line_number(text, match.start())
            type_ = self._classify_js_symbol(file, name, text[max(0, match.start() - 180): match.end() + 240], is_class=False)
            info.symbols.append(
                CodeSymbol(
                    id=self._symbol_id(file, name, line),
                    name=name,
                    type=type_,
                    file=file,
                    line=line,
                    language=info.language,
                    runtime_role=self._runtime_role(file, type_, []),
                    signature=f"const {name} = (...) =>",
                    imports=self._format_imports(info.imports),
                    calls=self._js_calls(text[match.end(): match.end() + 1800])[:80],
                    metadata={"exported": match.group(0).lstrip().startswith("export")},
                )
            )

        for match in re.finditer(
            r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*(create(?:Store|Slice|Context)?|configureStore|atom|selector|new\s+QueryClient|create)\s*\(",
            text,
        ):
            name = match.group(1)
            if any(symbol.name == name and symbol.file == file for symbol in info.symbols):
                continue
            line = self._line_number(text, match.start())
            type_ = self._classify_js_symbol(file, name, text[max(0, match.start() - 180): match.end() + 260], is_class=False)
            info.symbols.append(
                CodeSymbol(
                    id=self._symbol_id(file, name, line),
                    name=name,
                    type=type_,
                    file=file,
                    line=line,
                    language=info.language,
                    runtime_role=self._runtime_role(file, type_, []),
                    signature=f"const {name} = {match.group(2)}(...)",
                    imports=self._format_imports(info.imports),
                    calls=self._js_calls(text[match.end(): match.end() + 1600])[:80],
                    metadata={"exported": match.group(0).lstrip().startswith("export")},
                )
            )

        for match in re.finditer(r"(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)\b", text):
            self._append_ts_shape(info, file, text, match, "interface")
        for match in re.finditer(r"(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=", text):
            self._append_ts_shape(info, file, text, match, "schema")

        info.routes.extend(self._js_routes(file, text, info))
        self._ensure_next_route_symbols(file, text, info)
        return info

    def _append_ts_shape(self, info: FileIntelligence, file: str, text: str, match: re.Match[str], type_: str) -> None:
        name = match.group(1)
        line = self._line_number(text, match.start())
        info.symbols.append(
            CodeSymbol(
                id=self._symbol_id(file, name, line),
                name=name,
                type=type_,
                file=file,
                line=line,
                language=info.language,
                runtime_role=self._runtime_role(file, type_, []),
                signature=match.group(0).strip(),
                imports=self._format_imports(info.imports),
                metadata={"exported": match.group(0).lstrip().startswith("export")},
            )
        )

    @staticmethod
    def _js_imports(text: str) -> list[ImportReference]:
        imports: list[ImportReference] = []
        static_pattern = re.compile(
            r"import\s+(?:type\s+)?(?:(.*?)\s+from\s+)?['\"]([^'\"]+)['\"]",
            re.DOTALL,
        )
        export_pattern = re.compile(r"export\s+(?:type\s+)?(?:.*?)\s+from\s+['\"]([^'\"]+)['\"]", re.DOTALL)
        require_pattern = re.compile(r"(?:const|let|var)\s+([^=]+?)\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)")
        dynamic_pattern = re.compile(r"\bimport\(\s*['\"]([^'\"]+)['\"]\s*\)")

        for match in static_pattern.finditer(text):
            names = RepositoryCodeIntelligenceBuilder._js_imported_names(match.group(1) or "")
            imports.append(ImportReference(match.group(2), names, "static import"))
        for match in export_pattern.finditer(text):
            imports.append(ImportReference(match.group(1), [], "barrel export"))
        for match in require_pattern.finditer(text):
            imports.append(ImportReference(match.group(2), RepositoryCodeIntelligenceBuilder._js_imported_names(match.group(1)), "require"))
        for match in dynamic_pattern.finditer(text):
            imports.append(ImportReference(match.group(1), [], "dynamic import"))
        return imports

    @staticmethod
    def _js_imported_names(clause: str) -> list[str]:
        names: list[str] = []
        clean = clause.strip()
        if not clean:
            return names
        namespace = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clean)
        if namespace:
            names.append(namespace.group(1))
        default = re.match(r"([A-Za-z_$][\w$]*)", clean)
        if default and not clean.startswith("{"):
            names.append(default.group(1))
        for block in re.findall(r"\{([^}]+)\}", clean):
            for item in block.split(","):
                raw = item.strip()
                if not raw:
                    continue
                names.append(raw.split(" as ")[-1].strip())
        return list(dict.fromkeys(names))

    @staticmethod
    def _js_env_usage(text: str) -> list[str]:
        names = re.findall(r"\bprocess\.env\.([A-Z0-9_]+)\b", text)
        names.extend(re.findall(r"\bimport\.meta\.env\.([A-Z0-9_]+)\b", text))
        names.extend(re.findall(r"\bprocess\.env\[['\"]([A-Z0-9_]+)['\"]\]", text))
        return list(dict.fromkeys(names))

    @staticmethod
    def _js_calls(text: str) -> list[str]:
        calls = re.findall(r"\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*){0,3})\s*\(", text)
        ignored = {"if", "for", "while", "switch", "return", "function", "catch"}
        return list(dict.fromkeys(call for call in calls if call.split(".", 1)[0] not in ignored))

    def _js_routes(self, file: str, text: str, info: FileIntelligence) -> list[RouteEndpoint]:
        routes: list[RouteEndpoint] = []
        route_path = self._next_route_path(file)
        if route_path:
            for match in re.finditer(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD)\s*\(", text):
                method = match.group(1)
                line = self._line_number(text, match.start())
                middleware = self._middleware_from_text(text[: match.start()] + text[match.end(): match.end() + 800])
                auth_required = self._auth_required_from_terms(middleware + info.calls + info.imports_as_terms())
                routes.append(
                    RouteEndpoint(
                        id=self._route_id(method, route_path, file, line),
                        method=method,
                        path=route_path,
                        file=file,
                        line=line,
                        framework="Next.js",
                        controller=method,
                        middleware=middleware,
                        auth_required=auth_required,
                        dependencies=self._format_imports(info.imports),
                        symbols=[self._symbol_id(file, method, line)],
                        metadata={"runtime": "route-handler"},
                    )
                )
        elif self._pages_api_path(file):
            path = self._pages_api_path(file) or "/api"
            method = "ALL"
            routes.append(
                RouteEndpoint(
                    id=self._route_id(method, path, file, 1),
                    method=method,
                    path=path,
                    file=file,
                    line=1,
                    framework="Next.js",
                    controller="default",
                    middleware=self._middleware_from_text(text),
                    auth_required=self._auth_required_from_terms(info.calls + info.imports_as_terms()),
                    dependencies=self._format_imports(info.imports),
                    metadata={"runtime": "pages-api"},
                )
            )

        express_pattern = re.compile(
            r"\b(?:router|app|server)\.(get|post|put|patch|delete|options|head|all|use)\s*\(\s*['\"]([^'\"]+)['\"]\s*(?:,\s*([^;\n]+?))?\)",
            re.IGNORECASE | re.DOTALL,
        )
        for match in express_pattern.finditer(text):
            raw_method = match.group(1).upper()
            method = "MIDDLEWARE" if raw_method == "USE" else raw_method
            path = match.group(2)
            arg_text = match.group(3) or ""
            handlers = self._split_js_arguments(arg_text)
            middleware = [handler for handler in handlers[:-1] if handler]
            controller = handlers[-1] if handlers else None
            line = self._line_number(text, match.start())
            routes.append(
                RouteEndpoint(
                    id=self._route_id(method, path, file, line),
                    method=method,
                    path=path,
                    file=file,
                    line=line,
                    framework="Express",
                    controller=controller,
                    middleware=middleware,
                    auth_required=self._auth_required_from_terms(middleware + [controller or ""]),
                    dependencies=self._format_imports(info.imports),
                    metadata={"receiver": match.group(0).split(".", 1)[0]},
                )
            )
        return routes

    @staticmethod
    def _next_route_path(file: str) -> str | None:
        path = PurePosixPath(file)
        parts = list(path.parts)
        if path.name not in {"route.ts", "route.tsx", "route.js", "route.jsx"}:
            return None
        if "app" not in parts:
            return None
        app_index = parts.index("app")
        route_parts = parts[app_index + 1: -1]
        if not route_parts:
            return "/"
        normalized = [
            re.sub(r"^\[(.+)\]$", r":\1", part)
            for part in route_parts
            if not part.startswith("(")
        ]
        return "/" + "/".join(normalized)

    @staticmethod
    def _pages_api_path(file: str) -> str | None:
        path = PurePosixPath(file)
        parts = list(path.with_suffix("").parts)
        if "pages" not in parts:
            return None
        pages_index = parts.index("pages")
        route_parts = parts[pages_index + 1:]
        if not route_parts or route_parts[0] != "api":
            return None
        normalized = [re.sub(r"^\[(.+)\]$", r":\1", part) for part in route_parts]
        if normalized[-1] == "index":
            normalized = normalized[:-1]
        return "/" + "/".join(normalized)

    def _ensure_next_route_symbols(self, file: str, text: str, info: FileIntelligence) -> None:
        if not self._next_route_path(file):
            return
        existing = {symbol.name for symbol in info.symbols}
        for method in HTTP_METHODS:
            if method in existing:
                continue
            match = re.search(rf"export\s+(?:async\s+)?(?:const\s+)?{method}\b", text)
            if not match:
                continue
            line = self._line_number(text, match.start())
            info.symbols.append(
                CodeSymbol(
                    id=self._symbol_id(file, method, line),
                    name=method,
                    type="route",
                    file=file,
                    line=line,
                    language=info.language,
                    runtime_role="api route handler",
                    signature=f"export {method}",
                    imports=self._format_imports(info.imports),
                    calls=self._js_calls(text[match.end(): match.end() + 1800])[:80],
                    metadata={"framework": "Next.js"},
                )
            )

    @staticmethod
    def _split_js_arguments(arg_text: str) -> list[str]:
        if not arg_text:
            return []
        args: list[str] = []
        current: list[str] = []
        depth = 0
        quote = ""
        for char in arg_text:
            if quote:
                current.append(char)
                if char == quote:
                    quote = ""
                continue
            if char in {"'", '"', "`"}:
                quote = char
                current.append(char)
                continue
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)
            if char == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            args.append("".join(current).strip())
        return [re.sub(r"\s+", " ", arg).strip() for arg in args if arg.strip()]

    @staticmethod
    def _classify_python_symbol(file: str, name: str, evidence: list[str], calls: list[str], *, is_class: bool) -> str:
        text = " ".join([file, name, *evidence, *calls]).lower()
        if "middleware" in text or "oauth2passwordbearer" in text:
            return "middleware"
        if "basemodel" in text or "schema" in file.lower() or name.endswith(("Schema", "DTO", "Dto")):
            return "schema"
        if "model" in file.lower() or "sqlalchemy" in text or "declarative" in text:
            return "model"
        if "router." in text or "app." in text or "route" in PurePosixPath(file).name.lower():
            return "controller" if not is_class else "class"
        if "service" in file.lower() or name.lower().endswith("service"):
            return "service"
        if "controller" in file.lower() or name.lower().endswith("controller"):
            return "controller"
        if "provider" in text:
            return "provider"
        if "store" in text:
            return "store"
        return "class" if is_class else "function"

    @staticmethod
    def _classify_js_symbol(file: str, name: str, evidence: str, *, is_class: bool) -> str:
        text = f"{file} {name} {evidence}".lower()
        if "middleware" in text or name == "middleware":
            return "middleware"
        if name in HTTP_METHODS or "route.ts" in file or "route.js" in file:
            return "route"
        if "createstore" in text or "createslice" in text or "zustand" in text or "store" in text:
            return "store"
        if name.startswith("use") and len(name) > 3 and name[3].isupper():
            return "hook"
        if "createcontext" in text or name.endswith("Provider") or "provider" in text:
            return "provider"
        if "service" in text or name.lower().endswith("service"):
            return "service"
        if "controller" in text or name.lower().endswith("controller"):
            return "controller"
        if "z.object" in text or "schema" in text or name.endswith(("Schema", "Dto", "DTO")):
            return "schema"
        if "model" in PurePosixPath(file).name.lower() or name.endswith("Model"):
            return "model"
        return "class" if is_class else "function"

    @staticmethod
    def _runtime_role(file: str, symbol_type: str, decorators: list[str]) -> str | None:
        path = file.lower()
        decorator_text = " ".join(decorators).lower()
        if symbol_type in {"route", "controller"} or "router." in decorator_text or "app." in decorator_text:
            return "api request handling"
        if symbol_type == "middleware":
            return "request middleware"
        if symbol_type == "store":
            return "shared state"
        if symbol_type == "provider":
            return "runtime provider"
        if symbol_type in {"schema", "model"}:
            return "data contract"
        if "app/" in path or "/pages/" in path or "/components/" in path:
            return "frontend runtime"
        if "backend/" in path or "api/" in path or "server" in path:
            return "backend runtime"
        return None

    @staticmethod
    def _safe_unparse(node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return ""

    @staticmethod
    def _python_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        args = [arg.arg for arg in node.args.args]
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        return f"{prefix} {node.name}({', '.join(args)})"

    @staticmethod
    def _clean_params(params: str) -> str:
        return re.sub(r"\s+", " ", params).strip()[:160]

    @staticmethod
    def _line_number(text: str, index: int) -> int:
        return text.count("\n", 0, index) + 1

    @staticmethod
    def _compact_preview(text: str) -> str:
        stripped = re.sub(r"\s+", " ", text).strip()
        return stripped[:1200]

    @staticmethod
    def _format_imports(imports: list[ImportReference]) -> list[str]:
        formatted = []
        for import_ref in imports:
            if import_ref.imported_names:
                formatted.append(f"{import_ref.specifier}: {', '.join(import_ref.imported_names[:8])}")
            else:
                formatted.append(import_ref.specifier)
        return list(dict.fromkeys(formatted))[:80]

    @staticmethod
    def _middleware_from_text(text: str) -> list[str]:
        candidates = re.findall(r"\b([A-Za-z_$][\w$]*(?:Middleware|Auth|Guard|Policy|Permission|Role|Session|Token)[A-Za-z_$\w$]*)\b", text)
        candidates.extend(re.findall(r"\bDepends\(\s*([A-Za-z_][\w.]*)", text))
        return list(dict.fromkeys(candidates))[:12]

    @staticmethod
    def _auth_required_from_terms(terms: list[str]) -> bool:
        text = " ".join(str(term) for term in terms).lower()
        auth_terms = [
            "auth",
            "jwt",
            "token",
            "session",
            "user",
            "currentuser",
            "current_user",
            "permission",
            "role",
            "passport",
            "clerk",
            "firebase",
            "oauth",
            "guard",
        ]
        return any(term in text for term in auth_terms)

    @staticmethod
    def _text_signals(file: str, text: str) -> list[str]:
        lower = text.lower()
        signals: list[str] = []
        signal_map = {
            "jwt": "JWT token handling",
            "oauth": "OAuth flow",
            "passport": "Passport auth",
            "clerk": "Clerk auth",
            "firebase": "Firebase auth",
            "getserversession": "Auth.js session",
            "usequery": "React Query cache",
            "queryclient": "React Query cache",
            "createstore": "Redux-style store",
            "createslice": "Redux slice",
            "zustand": "Zustand store",
            "createcontext": "React Context",
            "process.env": "environment variables",
            "os.getenv": "environment variables",
        }
        for needle, signal in signal_map.items():
            if needle in lower:
                signals.append(f"{signal} in {file}")
        return list(dict.fromkeys(signals))

    def _connect_symbol_graph(self, symbols: list[CodeSymbol], parsed: dict[str, FileIntelligence]) -> None:
        symbols_by_name: defaultdict[str, list[CodeSymbol]] = defaultdict(list)
        symbols_by_file_name: dict[tuple[str, str], CodeSymbol] = {}
        for symbol in symbols:
            symbols_by_name[symbol.name].append(symbol)
            symbols_by_file_name[(symbol.file, symbol.name)] = symbol

        for symbol in symbols:
            seen_imports = set(symbol.imports)
            called_names = set()
            for call in symbol.calls:
                called_names.add(call)
                called_names.add(call.rsplit(".", 1)[-1])

            for called_name in sorted(called_names):
                target = symbols_by_file_name.get((symbol.file, called_name))
                if target and target.id != symbol.id:
                    self._link_symbols(symbol, target, seen_imports)
                elif called_name in symbols_by_name:
                    for target in symbols_by_name[called_name][:6]:
                        if target.id != symbol.id:
                            self._link_symbols(symbol, target, seen_imports)

            file_info = parsed.get(symbol.file)
            if not file_info:
                continue
            imported_names = {name for import_ref in file_info.imports for name in import_ref.imported_names}
            for imported_name in imported_names:
                for target in symbols_by_name.get(imported_name, [])[:4]:
                    if target.file != symbol.file:
                        self._link_symbols(symbol, target, seen_imports)

    @staticmethod
    def _link_symbols(source: CodeSymbol, target: CodeSymbol, seen_imports: set[str]) -> None:
        if target.id not in source.imports and target.id not in seen_imports:
            source.imports.append(target.id)
            seen_imports.add(target.id)
        if source.id not in target.used_by:
            target.used_by.append(source.id)

    def _auth_flow(
        self,
        scan: RepositoryScan,
        parsed: dict[str, FileIntelligence],
        symbols: list[CodeSymbol],
        routes: list[RouteEndpoint],
    ) -> AuthFlow:
        manifest_text = self._manifest_text(scan).lower()
        code_signals = " ".join(signal for info in parsed.values() for signal in info.signals).lower()
        all_text = f"{manifest_text} {code_signals}"
        strategies: list[str] = []
        strategy_needles = {
            "JWT": ["jsonwebtoken", "pyjwt", "python-jose", "jose", "jwt", "oauth2passwordbearer"],
            "sessions": ["express-session", "sessionmiddleware", "session", "getserversession"],
            "cookies": ["cookie", "set_cookie", "cookies()"],
            "OAuth": ["oauth", "oauth2", "openid"],
            "Auth.js": ["next-auth", "auth.js", "getserversession"],
            "Clerk": ["@clerk", "clerk"],
            "Firebase auth": ["firebase/auth", "firebase-admin"],
            "Passport": ["passport"],
            "RBAC": ["rbac", "role", "permission", "hasrole", "is_admin"],
        }
        for strategy, needles in strategy_needles.items():
            if any(needle in all_text for needle in needles):
                strategies.append(strategy)

        auth_symbols = [
            symbol
            for symbol in symbols
            if self._auth_required_from_terms([symbol.name, symbol.type, symbol.file, *symbol.calls, *symbol.decorators])
        ]
        token_issuers = [
            symbol.id
            for symbol in auth_symbols
            if self._matches_any([symbol.name, *symbol.calls], ["sign", "encode", "create_access_token", "create_token", "jwt.sign"])
        ]
        validators = [
            symbol.id
            for symbol in auth_symbols
            if symbol.type == "middleware"
            or self._matches_any([symbol.name, *symbol.calls, *symbol.decorators], ["verify", "decode", "get_current_user", "requireauth", "authmiddleware", "oauth2passwordbearer"])
        ]
        role_enforcement = [
            symbol.id
            for symbol in auth_symbols
            if self._matches_any([symbol.name, *symbol.calls, *symbol.decorators, symbol.file], ["role", "permission", "rbac", "admin", "authorize", "policy"])
        ]
        session_persistence = sorted(
            {
                f"{info.file}: {env}"
                for info in parsed.values()
                for env in info.env
                if any(term in env.lower() for term in ("jwt", "session", "secret", "token", "auth", "cookie"))
            }
        )[:20]
        login_routes = [route for route in routes if re.search(r"/(login|signin|sign-in|auth|token|session)", route.path, re.IGNORECASE) or self._matches_any([route.controller or ""], ["login", "signin", "token"])]
        protected_routes = [route for route in routes if route.auth_required]
        files = sorted({symbol.file for symbol in auth_symbols} | {route.file for route in login_routes + protected_routes})[:80]

        if not strategies and auth_symbols:
            strategies.append("custom auth")
        explanation = self._auth_explanation(strategies, login_routes, token_issuers, validators, protected_routes, symbols)
        confidence = "high" if strategies and (validators or protected_routes or login_routes) else "medium" if auth_symbols or strategies else "low"
        return AuthFlow(
            strategies=strategies,
            files=files,
            login_routes=login_routes[:40],
            token_issuers=token_issuers[:40],
            validators=validators[:40],
            protected_routes=protected_routes[:80],
            role_enforcement=role_enforcement[:40],
            session_persistence=session_persistence,
            explanation=explanation,
            confidence=confidence,
        )

    @staticmethod
    def _auth_explanation(
        strategies: list[str],
        login_routes: list[RouteEndpoint],
        token_issuers: list[str],
        validators: list[str],
        protected_routes: list[RouteEndpoint],
        symbols: list[CodeSymbol],
    ) -> str:
        symbol_by_id = {symbol.id: symbol for symbol in symbols}
        if not strategies:
            return "No explicit authentication strategy was detected from routes, middleware, dependencies, or auth-like symbols."
        parts = [f"Authentication evidence points to {', '.join(strategies)}."]
        if login_routes:
            parts.append(
                "Login/session entrypoints include "
                + ", ".join(f"{route.method} {route.path} in {route.file}" for route in login_routes[:4])
                + "."
            )
        if token_issuers:
            issuer_names = [
                f"{symbol_by_id[item].name} in {symbol_by_id[item].file}"
                for item in token_issuers[:4]
                if item in symbol_by_id
            ]
            if issuer_names:
                parts.append("Token/session issuance is likely handled by " + ", ".join(issuer_names) + ".")
        if validators:
            validator_names = [
                f"{symbol_by_id[item].name} in {symbol_by_id[item].file}"
                for item in validators[:4]
                if item in symbol_by_id
            ]
            if validator_names:
                parts.append("Request validation is enforced through " + ", ".join(validator_names) + ".")
        if protected_routes:
            parts.append(f"{len(protected_routes)} route(s) carry auth-like middleware or dependency evidence.")
        return " ".join(parts)

    def _state_flow(self, scan: RepositoryScan, symbols: list[CodeSymbol], parsed: dict[str, FileIntelligence]) -> StateFlow:
        manifest_text = self._manifest_text(scan).lower()
        signal_text = " ".join(signal for info in parsed.values() for signal in info.signals).lower()
        all_text = f"{manifest_text} {signal_text}"
        library_needles = {
            "Redux": ["redux", "@reduxjs/toolkit", "configurestore", "createslice"],
            "Zustand": ["zustand"],
            "Context API": ["createcontext", "usecontext"],
            "React Query": ["@tanstack/react-query", "react-query", "usequery", "queryclient"],
            "MobX": ["mobx"],
            "Recoil": ["recoil"],
            "SWR": ["swr", "useswr"],
        }
        libraries = [library for library, needles in library_needles.items() if any(needle in all_text for needle in needles)]
        stores = [symbol for symbol in symbols if symbol.type == "store" or self._matches_any([symbol.name, symbol.file], ["store", "slice", "reducer"])]
        providers = [symbol for symbol in symbols if symbol.type == "provider"]
        hooks = [symbol for symbol in symbols if symbol.type == "hook"]
        cache_layers = [
            symbol
            for symbol in symbols
            if self._matches_any([symbol.name, symbol.file, *symbol.calls, *symbol.imports], ["query", "cache", "swr", "useQuery", "QueryClient"])
        ]
        boundaries = sorted({PurePosixPath(symbol.file).parts[0] for symbol in stores + providers + hooks if PurePosixPath(symbol.file).parts})[:20]
        relationships = self._state_relationships(stores, providers, hooks, cache_layers)
        explanation = self._state_explanation(libraries, stores, providers, hooks, cache_layers)
        confidence = "high" if libraries and (stores or providers or hooks) else "medium" if stores or providers or hooks else "low"
        return StateFlow(
            libraries=libraries,
            stores=stores[:80],
            providers=providers[:80],
            hooks=hooks[:120],
            cache_layers=cache_layers[:80],
            shared_state_boundaries=boundaries,
            relationships=relationships[:120],
            explanation=explanation,
            confidence=confidence,
        )

    @staticmethod
    def _state_relationships(
        stores: list[CodeSymbol],
        providers: list[CodeSymbol],
        hooks: list[CodeSymbol],
        cache_layers: list[CodeSymbol],
    ) -> list[dict[str, Any]]:
        relationships: list[dict[str, Any]] = []
        for provider in providers[:40]:
            for hook in hooks[:60]:
                if provider.file == hook.file or provider.name.lower().replace("provider", "") in hook.name.lower():
                    relationships.append({"source": provider.id, "target": hook.id, "kind": "provides state to hook"})
        for store in stores[:40]:
            for hook in hooks[:60]:
                if store.name.lower().replace("store", "") in hook.name.lower() or store.id in hook.imports:
                    relationships.append({"source": hook.id, "target": store.id, "kind": "reads store"})
        for cache in cache_layers[:40]:
            relationships.append({"source": cache.id, "target": "remote data", "kind": "cache layer"})
        return relationships

    @staticmethod
    def _state_explanation(
        libraries: list[str],
        stores: list[CodeSymbol],
        providers: list[CodeSymbol],
        hooks: list[CodeSymbol],
        cache_layers: list[CodeSymbol],
    ) -> str:
        if not any([libraries, stores, providers, hooks, cache_layers]):
            return "No explicit Redux, Zustand, Context API, React Query, MobX, Recoil, or SWR state layer was detected."
        parts = []
        if libraries:
            parts.append(f"State management evidence includes {', '.join(libraries)}.")
        if stores:
            parts.append("Stores include " + ", ".join(f"{symbol.name} in {symbol.file}" for symbol in stores[:4]) + ".")
        if providers:
            parts.append("Provider boundaries include " + ", ".join(f"{symbol.name} in {symbol.file}" for symbol in providers[:4]) + ".")
        if hooks:
            parts.append("State-facing hooks include " + ", ".join(f"{symbol.name} in {symbol.file}" for symbol in hooks[:4]) + ".")
        if cache_layers:
            parts.append(f"{len(cache_layers)} cache/query layer symbol(s) were detected.")
        return " ".join(parts)

    def _runtime_map(
        self,
        scan: RepositoryScan,
        architecture: ArchitectureMap | None,
        symbols: list[CodeSymbol],
        routes: list[RouteEndpoint],
        parsed: dict[str, FileIntelligence],
    ) -> dict[str, Any]:
        entry_symbols = [symbol for symbol in symbols if symbol.file in scan.entry_points][:120]
        boundary_files: defaultdict[str, list[str]] = defaultdict(list)
        for symbol in symbols:
            role = symbol.runtime_role or "source"
            if len(boundary_files[role]) < 30:
                boundary_files[role].append(symbol.file)
        graph_metrics = architecture.graph_metrics if architecture else {}
        return {
            "entry_points": scan.entry_points,
            "entry_symbols": [symbol.model_dump(mode="json") for symbol in entry_symbols[:40]],
            "runtime_roles": {role: sorted(set(files)) for role, files in boundary_files.items()},
            "route_count": len(routes),
            "environment_usage": sorted({env for info in parsed.values() for env in info.env})[:80],
            "frameworks": scan.frameworks,
            "dependency_graph": graph_metrics,
        }

    @staticmethod
    def _deployment_map(scan: RepositoryScan) -> dict[str, Any]:
        deployment_files = [
            file
            for file in scan.files
            if PurePosixPath(file).name
            in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", "render.yaml", "render.yml", "vercel.json"}
            or file.startswith(".github/workflows/")
        ]
        hosting = []
        if "render.yaml" in {PurePosixPath(file).name for file in deployment_files}:
            hosting.append("Render")
        if "vercel.json" in {PurePosixPath(file).name for file in deployment_files}:
            hosting.append("Vercel")
        if any(file.startswith(".github/workflows/") for file in deployment_files):
            hosting.append("GitHub Actions")
        if any(PurePosixPath(file).name.startswith("Dockerfile") or "docker-compose" in PurePosixPath(file).name for file in deployment_files):
            hosting.append("Docker")
        return {
            "files": deployment_files[:80],
            "targets": hosting,
            "manifests": {
                file: scan.manifests.get(file)
                for file in deployment_files
                if file in scan.manifests
            },
        }

    def _semantic_memory(
        self,
        scan: RepositoryScan,
        architecture: ArchitectureMap | None,
        symbols: list[CodeSymbol],
        routes: list[RouteEndpoint],
        auth: AuthFlow,
        state: StateFlow,
        runtime: dict[str, Any],
        deployment: dict[str, Any],
        parsed: dict[str, FileIntelligence],
    ) -> list[SemanticMemoryItem]:
        items: list[SemanticMemoryItem] = []
        for symbol in sorted(symbols, key=self._symbol_importance, reverse=True)[:600]:
            summary = self._symbol_summary(symbol)
            items.append(
                self._memory_item(
                    type_="symbol",
                    title=f"{symbol.type}: {symbol.name}",
                    summary=summary,
                    file=symbol.file,
                    line=symbol.line,
                    symbol=symbol.id,
                    importance=self._symbol_importance(symbol),
                    relations=symbol.imports[:12] + symbol.used_by[:12],
                    metadata={"runtime_role": symbol.runtime_role, "language": symbol.language},
                )
            )
        for route in routes[:400]:
            auth_text = " protected" if route.auth_required else ""
            summary = f"{route.framework}{auth_text} route {route.method} {route.path} handled by {route.controller or 'inline handler'} in {route.file}."
            if route.middleware:
                summary += f" Middleware/dependencies: {', '.join(route.middleware[:6])}."
            items.append(
                self._memory_item(
                    type_="route",
                    title=f"{route.method} {route.path}",
                    summary=summary,
                    file=route.file,
                    line=route.line,
                    route=route.id,
                    importance=9.0 if route.auth_required else 7.0,
                    relations=route.symbols + route.dependencies[:8],
                    metadata={"framework": route.framework, "auth_required": route.auth_required},
                )
            )
        if auth.files or auth.strategies:
            items.append(
                self._memory_item(
                    type_="auth",
                    title="Authentication flow",
                    summary=auth.explanation,
                    file=auth.files[0] if auth.files else None,
                    importance=10.0,
                    relations=auth.token_issuers[:8] + auth.validators[:8],
                    metadata=auth.model_dump(mode="json", exclude={"login_routes", "protected_routes"}),
                )
            )
        if state.libraries or state.stores or state.providers or state.hooks:
            state_files = [symbol.file for symbol in state.stores + state.providers + state.hooks]
            items.append(
                self._memory_item(
                    type_="state",
                    title="Frontend state flow",
                    summary=state.explanation,
                    file=state_files[0] if state_files else None,
                    importance=8.5,
                    relations=[symbol.id for symbol in state.stores[:8] + state.providers[:8] + state.hooks[:8]],
                    metadata={"libraries": state.libraries, "boundaries": state.shared_state_boundaries},
                )
            )
        if architecture:
            items.append(
                self._memory_item(
                    type_="architecture",
                    title="Runtime architecture",
                    summary=architecture.summary,
                    importance=8.0,
                    relations=[f"{edge.source}->{edge.target}" for edge in architecture.edges[:20]],
                    metadata={
                        "boundaries": architecture.boundaries,
                        "dependency_flow": architecture.dependency_flow,
                        "graph_metrics": architecture.graph_metrics,
                    },
                )
            )
        if deployment.get("files"):
            items.append(
                self._memory_item(
                    type_="deployment",
                    title="Deployment topology",
                    summary=f"Deployment topology is described by {', '.join(deployment.get('files', [])[:8])}; detected targets: {', '.join(deployment.get('targets', []) or ['configuration files'])}.",
                    file=deployment["files"][0],
                    importance=7.5,
                    relations=deployment.get("files", [])[:12],
                    metadata=deployment,
                )
            )
        for file, info in parsed.items():
            if info.env:
                items.append(
                    self._memory_item(
                        type_="environment",
                        title=f"Environment usage in {file}",
                        summary=f"{file} reads environment variables: {', '.join(info.env[:12])}.",
                        file=file,
                        importance=6.5,
                        relations=info.env[:20],
                        metadata={"env": info.env},
                    )
                )
        for entry in scan.entry_points[:30]:
            info = parsed.get(entry)
            if not info:
                continue
            items.append(
                self._memory_item(
                    type_="entrypoint",
                    title=f"Runtime entrypoint {entry}",
                    summary=f"{entry} is a runtime entry point with imports {', '.join(self._format_imports(info.imports)[:8]) or 'none detected'} and symbols {', '.join(symbol.name for symbol in info.symbols[:8]) or 'none detected'}.",
                    file=entry,
                    importance=8.0,
                    relations=[symbol.id for symbol in info.symbols[:12]],
                    metadata={"signals": info.signals, "environment": info.env},
                )
            )
        return sorted(items, key=lambda item: item.importance, reverse=True)

    def _memory_item(
        self,
        *,
        type_: str,
        title: str,
        summary: str,
        file: str | None = None,
        line: int | None = None,
        symbol: str | None = None,
        route: str | None = None,
        importance: float = 0.0,
        relations: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SemanticMemoryItem:
        seed = f"{type_}:{title}:{file}:{line}:{symbol}:{route}"
        keywords = self._keywords(" ".join([title, summary, file or "", symbol or "", route or ""]))
        return SemanticMemoryItem(
            id=hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16],
            type=type_,
            title=title,
            file=file,
            line=line,
            symbol=symbol,
            route=route,
            summary=summary,
            keywords=keywords,
            importance=round(importance, 3),
            relations=list(dict.fromkeys(relations or []))[:40],
            metadata=metadata or {},
        )

    @staticmethod
    def _symbol_summary(symbol: CodeSymbol) -> str:
        parts = [f"{symbol.name} is a {symbol.type} in {symbol.file}"]
        if symbol.line:
            parts[0] += f":{symbol.line}"
        if symbol.runtime_role:
            parts.append(f"runtime role: {symbol.runtime_role}")
        if symbol.signature:
            parts.append(f"signature: {symbol.signature}")
        if symbol.imports:
            parts.append(f"imports/uses: {', '.join(symbol.imports[:8])}")
        if symbol.used_by:
            parts.append(f"used by {len(symbol.used_by)} symbol(s)")
        return ". ".join(parts) + "."

    @staticmethod
    def _symbol_importance(symbol: CodeSymbol) -> float:
        score = 1.0
        score += len(symbol.used_by) * 0.8
        score += len(symbol.imports) * 0.25
        score += 3.0 if symbol.type in {"middleware", "route", "controller", "store", "provider", "service"} else 0.0
        score += 1.5 if symbol.runtime_role else 0.0
        score += 1.0 if symbol.file.lower().endswith(("main.py", "app.py", "server.ts", "server.js", "route.ts", "route.js")) else 0.0
        return score

    def _symbol_graph(self, symbols: list[CodeSymbol], routes: list[RouteEndpoint], parsed: dict[str, FileIntelligence]) -> dict[str, Any]:
        edges = []
        for symbol in symbols:
            for target in symbol.imports[:80]:
                if target.startswith(("static import", "python import")):
                    continue
                if ":" in target and "/" not in target:
                    continue
                edges.append({"source": symbol.id, "target": target, "kind": "uses"})
        ownership: defaultdict[str, list[str]] = defaultdict(list)
        for symbol in symbols:
            root = PurePosixPath(symbol.file).parts[0] if PurePosixPath(symbol.file).parts else "root"
            if len(ownership[root]) < 80:
                ownership[root].append(symbol.id)
        runtime_roles: defaultdict[str, list[str]] = defaultdict(list)
        for symbol in symbols:
            if symbol.runtime_role and len(runtime_roles[symbol.runtime_role]) < 80:
                runtime_roles[symbol.runtime_role].append(symbol.id)
        return {
            "nodes": len(symbols),
            "edges": edges[:3000],
            "ownership": dict(ownership),
            "runtime_roles": dict(runtime_roles),
            "route_symbols": {route.id: route.symbols for route in routes},
            "file_imports": {
                file: self._format_imports(info.imports)[:40]
                for file, info in parsed.items()
                if info.imports
            },
        }

    @staticmethod
    def _manifest_text(scan: RepositoryScan) -> str:
        return " ".join(str(value) for value in scan.manifests.values())

    @staticmethod
    def _matches_any(values: list[str], needles: list[str]) -> bool:
        text = " ".join(str(value) for value in values).lower()
        return any(needle.lower() in text for needle in needles)

    @staticmethod
    def _symbol_id(file: str, name: str, line: int | None) -> str:
        return f"{file}::{name}:{line or 1}"

    @staticmethod
    def _route_id(method: str, path: str, file: str, line: int | None) -> str:
        return f"{method.upper()} {path}::{file}:{line or 1}"

    @staticmethod
    def _keywords(text: str) -> list[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_]{1,}", text)
        expanded: list[str] = []
        for word in words:
            expanded.append(word.lower())
            expanded.extend(part.lower() for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", word))
        counts = Counter(word for word in expanded if word and word not in STOP_WORDS)
        return [word for word, _ in counts.most_common(30)]

    @staticmethod
    def _confidence(
        symbols: list[CodeSymbol],
        routes: list[RouteEndpoint],
        auth: AuthFlow,
        state: StateFlow,
        parsed: dict[str, FileIntelligence],
    ) -> str:
        score = 0
        score += 25 if symbols else 0
        score += 20 if len(symbols) >= 12 else min(15, len(symbols))
        score += 15 if routes else 0
        score += 15 if auth.confidence != "low" else 0
        score += 10 if state.confidence != "low" else 0
        score += 15 if parsed else 0
        if score >= 60:
            return "high"
        if score >= 30:
            return "medium"
        return "low"


class RepositorySemanticRetriever:
    def build_context(self, message: str, analysis: dict[str, Any], limit: int = 12) -> dict[str, Any]:
        code = RepositoryCodeIntelligence.model_validate(analysis.get("code_intelligence") or {})
        items = self.retrieve(message, code, limit=limit)
        symbols = self._symbols_for_items(items, code)
        routes = self._routes_for_items(items, code, message)
        return {
            "question": message,
            "retrieved_items": [item.model_dump(mode="json") for item in items],
            "symbols": [symbol.model_dump(mode="json") for symbol in symbols[:20]],
            "routes": [route.model_dump(mode="json") for route in routes[:20]],
            "auth": code.auth.model_dump(mode="json"),
            "state": code.state.model_dump(mode="json"),
            "runtime": code.runtime,
            "deployment": code.deployment,
            "architecture": {
                "summary": analysis.get("architecture", {}).get("summary"),
                "dependency_flow": analysis.get("architecture", {}).get("dependency_flow", []),
                "graph_metrics": analysis.get("architecture", {}).get("graph_metrics", {}),
                "topology": analysis.get("architecture", {}).get("topology", {}),
            },
        }

    def retrieve(self, message: str, code: RepositoryCodeIntelligence, limit: int = 12) -> list[SemanticMemoryItem]:
        query_terms = self._term_counts(message)
        intent_boosts = self._intent_boosts(message)
        scored: list[tuple[float, SemanticMemoryItem]] = []
        for item in code.semantic_memory:
            item_terms = Counter(item.keywords)
            item_terms.update(self._term_counts(" ".join([item.title, item.summary, item.file or "", item.symbol or "", item.route or ""])))
            score = self._cosine(query_terms, item_terms)
            score += item.importance / 100
            score += intent_boosts.get(item.type, 0.0)
            if item.file and item.file.lower() in message.lower():
                score += 0.35
            if item.symbol and item.symbol.lower() in message.lower():
                score += 0.25
            if score > 0:
                scored.append((score, item))
        return [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]

    def answer(self, repo_id: str, message: str, analysis: dict[str, Any]) -> ChatResponse:
        code = RepositoryCodeIntelligence.model_validate(analysis.get("code_intelligence") or {})
        context = self.build_context(message, analysis)
        lower = message.lower()
        if any(term in lower for term in ("auth", "login", "logout", "session", "jwt", "token", "protected", "permission", "role")):
            return self._answer_auth(repo_id, code, context)
        if any(term in lower for term in ("api", "route", "endpoint", "controller", "request", "response")):
            return self._answer_api(repo_id, code, context)
        if any(term in lower for term in ("state", "redux", "zustand", "provider", "context", "query", "store", "hook", "swr")):
            return self._answer_state(repo_id, code, context)
        if any(term in lower for term in ("deploy", "deployment", "runtime", "topology", "architecture", "boundary", "service")):
            return self._answer_architecture(repo_id, code, context, analysis)
        if any(term in lower for term in ("dependency", "import", "graph", "critical", "prisma", "database", "db", "schema", "model")):
            return self._answer_dependency(repo_id, code, context, analysis)
        if any(term in lower for term in ("onboard", "beginner", "start", "first", "walkthrough")):
            return self._answer_onboarding(repo_id, code, context, analysis)
        return self._answer_retrieval(repo_id, code, context)

    def _answer_auth(self, repo_id: str, code: RepositoryCodeIntelligence, context: dict[str, Any]) -> ChatResponse:
        auth = code.auth
        files = self._unique_files_from_routes(auth.login_routes + auth.protected_routes)
        files.extend(file for file in auth.files if file not in files)
        symbol_by_id = {symbol.id: symbol for symbol in code.symbols}
        cited_symbols = [symbol_by_id[item].id for item in auth.token_issuers + auth.validators + auth.role_enforcement if item in symbol_by_id][:12]
        cited_routes = [f"{route.method} {route.path}" for route in auth.login_routes[:8] + auth.protected_routes[:8]]
        if auth.confidence == "low":
            answer = "\n".join(
                [
                    "## Authentication",
                    "I could not find symbol-level evidence for a concrete auth flow. No login routes, auth middleware, JWT/session libraries, or protected route dependencies were detected in the indexed code.",
                    "",
                    "Grounding checked: route registry, middleware symbols, auth-like dependencies, token/session calls, and environment usage.",
                ]
            )
        else:
            lines = [
                "## Authentication",
                auth.explanation,
                "",
                f"Detected strategy: {', '.join(auth.strategies) if auth.strategies else 'custom auth signals'}",
            ]
            if auth.login_routes:
                lines.extend(["", "Login/session routes:"] + [f"- `{route.method} {route.path}` in `{route.file}` via `{route.controller or 'inline handler'}`" for route in auth.login_routes[:8]])
            if auth.protected_routes:
                lines.extend(["", "Protected routes:"] + [f"- `{route.method} {route.path}` in `{route.file}` uses {', '.join(route.middleware[:4]) or 'auth-like dependencies'}" for route in auth.protected_routes[:10]])
            if cited_symbols:
                lines.extend(["", "Auth symbols:"] + [f"- `{symbol_by_id[item].name}` in `{symbol_by_id[item].file}`" for item in cited_symbols if item in symbol_by_id][:10])
            if auth.session_persistence:
                lines.extend(["", "Session/token configuration:"] + [f"- `{item}`" for item in auth.session_persistence[:6]])
            answer = "\n".join(lines)
        return ChatResponse(
            repo_id=repo_id,
            answer=answer,
            cited_files=files[:12],
            cited_symbols=cited_symbols,
            cited_routes=cited_routes[:16],
            context_items=[SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"][:6]],
            confidence=auth.confidence,
        )

    def _answer_api(self, repo_id: str, code: RepositoryCodeIntelligence, context: dict[str, Any]) -> ChatResponse:
        routes = code.routes or self._routes_for_items([SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"]], code, "")
        files = self._unique_files_from_routes(routes)
        if not routes:
            answer = (
                "## API Surface\n"
                "I could not find concrete framework route definitions in the indexed code. "
                "The route extractor checked FastAPI decorators, Express router/app calls, Next.js route handlers, and pages API files."
            )
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=[], confidence="low", context_items=[SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"][:6]])
        grouped: defaultdict[str, list[RouteEndpoint]] = defaultdict(list)
        for route in routes:
            grouped[route.framework].append(route)
        lines = ["## API Surface", f"I found {len(routes)} concrete route definition(s) across {', '.join(sorted(grouped))}."]
        for framework, framework_routes in sorted(grouped.items()):
            lines.extend(["", f"{framework}:"])
            for route in framework_routes[:14]:
                auth = " protected" if route.auth_required else ""
                controller = f" -> `{route.controller}`" if route.controller else ""
                middleware = f" middleware: {', '.join(route.middleware[:4])}" if route.middleware else ""
                lines.append(f"- `{route.method} {route.path}`{auth} in `{route.file}`{controller}{middleware}")
        cited_routes = [f"{route.method} {route.path}" for route in routes[:24]]
        cited_symbols = [symbol for route in routes for symbol in route.symbols][:20]
        return ChatResponse(
            repo_id=repo_id,
            answer="\n".join(lines),
            cited_files=files[:16],
            cited_symbols=cited_symbols,
            cited_routes=cited_routes,
            context_items=[SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"][:6]],
            confidence="high" if len(routes) >= 3 else "medium",
        )

    def _answer_state(self, repo_id: str, code: RepositoryCodeIntelligence, context: dict[str, Any]) -> ChatResponse:
        state = code.state
        files = list(dict.fromkeys(symbol.file for symbol in state.stores + state.providers + state.hooks + state.cache_layers))[:16]
        cited_symbols = [symbol.id for symbol in state.stores[:8] + state.providers[:8] + state.hooks[:8] + state.cache_layers[:8]]
        if state.confidence == "low":
            answer = "\n".join(
                [
                    "## State Management",
                    "I could not find explicit Redux, Zustand, Context API, React Query, MobX, Recoil, or SWR evidence in code symbols or manifests.",
                    "",
                    "Grounding checked: store/provider/hook symbols, package manifests, cache/query calls, and shared state file boundaries.",
                ]
            )
        else:
            lines = [
                "## State Management",
                state.explanation,
                "",
                f"Detected libraries: {', '.join(state.libraries) if state.libraries else 'custom state symbols'}",
            ]
            if state.stores:
                lines.extend(["", "Stores:"] + [f"- `{symbol.name}` in `{symbol.file}`" for symbol in state.stores[:10]])
            if state.providers:
                lines.extend(["", "Providers:"] + [f"- `{symbol.name}` in `{symbol.file}`" for symbol in state.providers[:10]])
            if state.hooks:
                lines.extend(["", "Hooks:"] + [f"- `{symbol.name}` in `{symbol.file}`" for symbol in state.hooks[:12]])
            if state.cache_layers:
                lines.extend(["", "Cache/query layer:"] + [f"- `{symbol.name}` in `{symbol.file}`" for symbol in state.cache_layers[:8]])
            answer = "\n".join(lines)
        return ChatResponse(
            repo_id=repo_id,
            answer=answer,
            cited_files=files,
            cited_symbols=cited_symbols,
            context_items=[SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"][:6]],
            confidence=state.confidence,
        )

    def _answer_architecture(self, repo_id: str, code: RepositoryCodeIntelligence, context: dict[str, Any], analysis: dict[str, Any]) -> ChatResponse:
        architecture = analysis.get("architecture", {})
        runtime = code.runtime
        deployment = code.deployment
        entry_points = runtime.get("entry_points", [])
        files = list(dict.fromkeys(entry_points + deployment.get("files", [])))[:16]
        lines = [
            "## Runtime Architecture",
            architecture.get("summary") or "Architecture evidence comes from runtime entrypoints, symbol roles, dependency graph metrics, and deployment configuration.",
        ]
        roles = runtime.get("runtime_roles", {})
        if roles:
            lines.extend(["", "Runtime roles:"] + [f"- {role}: {', '.join(sorted(set(files_))[:5])}" for role, files_ in list(roles.items())[:8]])
        if architecture.get("dependency_flow"):
            lines.extend(["", "Dependency flow:"] + [f"- {item}" for item in architecture["dependency_flow"][:6]])
        if deployment.get("files"):
            lines.extend(["", "Deployment topology:"] + [f"- `{file}`" for file in deployment["files"][:10]])
        if entry_points:
            lines.extend(["", "Onboarding entrypoints:"] + [f"- `{file}`" for file in entry_points[:8]])
        return ChatResponse(
            repo_id=repo_id,
            answer="\n".join(lines),
            cited_files=files,
            context_items=[SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"][:6]],
            confidence=code.confidence,
        )

    def _answer_dependency(self, repo_id: str, code: RepositoryCodeIntelligence, context: dict[str, Any], analysis: dict[str, Any]) -> ChatResponse:
        architecture = analysis.get("architecture", {})
        graph_metrics = architecture.get("graph_metrics", {})
        edges = architecture.get("edges", [])
        schema_symbols = [symbol for symbol in code.symbols if symbol.type in {"schema", "model"} or self._matches_query(["schema", "model", "prisma", "database", "db"], [symbol.name, symbol.file, *symbol.imports])]
        files = list(dict.fromkeys([symbol.file for symbol in schema_symbols] + [file for item in context["retrieved_items"] for file in [item.get("file")] if file]))[:16]
        lines = [
            "## Dependency And Data Flow",
            f"Import tracing resolved {graph_metrics.get('imports_resolved', 0)} import(s) into {graph_metrics.get('edges', 0)} architecture edge(s).",
        ]
        if graph_metrics.get("internal_import_edges"):
            lines.append(f"Internal folder aggregation promoted {graph_metrics.get('internal_import_edges')} same-boundary import relationship(s).")
        if edges:
            lines.extend(["", "Strong relationships:"] + [f"- `{edge.get('source')}` -> `{edge.get('target')}` ({edge.get('kind')}, weight {edge.get('weight')})" for edge in edges[:10]])
        if schema_symbols:
            lines.extend(["", "Data/schema symbols:"] + [f"- `{symbol.name}` ({symbol.type}) in `{symbol.file}`" for symbol in schema_symbols[:12]])
        return ChatResponse(
            repo_id=repo_id,
            answer="\n".join(lines),
            cited_files=files,
            cited_symbols=[symbol.id for symbol in schema_symbols[:16]],
            context_items=[SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"][:6]],
            confidence="high" if graph_metrics.get("imports_resolved") or schema_symbols else "medium",
        )

    def _answer_onboarding(self, repo_id: str, code: RepositoryCodeIntelligence, context: dict[str, Any], analysis: dict[str, Any]) -> ChatResponse:
        contributor = analysis.get("contributor_plan", {})
        roadmap = contributor.get("roadmap", [])
        runtime = code.runtime
        entry_points = runtime.get("entry_points", [])
        files = list(dict.fromkeys(entry_points + [file for step in roadmap[:4] for file in step.get("files", [])]))[:16]
        lines = ["## Onboarding Path"]
        if entry_points:
            lines.extend(["Start with runtime entrypoints:"] + [f"- `{file}`" for file in entry_points[:6]])
        if roadmap:
            lines.extend(["", "Then follow the contributor sequence:"] + [f"{index + 1}. {step.get('title')}: {step.get('description')}" for index, step in enumerate(roadmap[:5])])
        else:
            lines.append("Use the cited entrypoints and symbol previews to trace one request or UI flow before changing code.")
        important_symbols = sorted(code.symbols, key=lambda symbol: len(symbol.used_by) + len(symbol.imports), reverse=True)[:10]
        if important_symbols:
            lines.extend(["", "High-leverage symbols to recognize:"] + [f"- `{symbol.name}` ({symbol.type}) in `{symbol.file}`" for symbol in important_symbols[:8]])
        return ChatResponse(
            repo_id=repo_id,
            answer="\n".join(lines),
            cited_files=files,
            cited_symbols=[symbol.id for symbol in important_symbols[:12]],
            context_items=[SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"][:6]],
            confidence=contributor.get("confidence", code.confidence),
        )

    def _answer_retrieval(self, repo_id: str, code: RepositoryCodeIntelligence, context: dict[str, Any]) -> ChatResponse:
        items = [SemanticMemoryItem.model_validate(item) for item in context["retrieved_items"]]
        if not items:
            answer = "I do not have symbol-level evidence for that question yet. Re-run analysis after the repository is available so I can retrieve exact files, symbols, routes, and runtime relationships."
            return ChatResponse(repo_id=repo_id, answer=answer, cited_files=[], confidence="low")
        lines = ["## Grounded Repository Answer", "The strongest code-level evidence I found:"]
        for item in items[:8]:
            location = f" in `{item.file}`" if item.file else ""
            lines.append(f"- {item.title}{location}: {item.summary}")
        files = list(dict.fromkeys(item.file for item in items if item.file))[:12]
        symbols = list(dict.fromkeys(item.symbol for item in items if item.symbol))[:12]
        routes = list(dict.fromkeys(item.title for item in items if item.type == "route"))[:12]
        return ChatResponse(
            repo_id=repo_id,
            answer="\n".join(lines),
            cited_files=files,
            cited_symbols=symbols,
            cited_routes=routes,
            context_items=items[:6],
            confidence=code.confidence,
        )

    @staticmethod
    def _unique_files_from_routes(routes: list[RouteEndpoint]) -> list[str]:
        return list(dict.fromkeys(route.file for route in routes if route.file))

    @staticmethod
    def _symbols_for_items(items: list[SemanticMemoryItem], code: RepositoryCodeIntelligence) -> list[CodeSymbol]:
        symbol_by_id = {symbol.id: symbol for symbol in code.symbols}
        symbols = []
        for item in items:
            if item.symbol and item.symbol in symbol_by_id:
                symbols.append(symbol_by_id[item.symbol])
            for relation in item.relations:
                if relation in symbol_by_id:
                    symbols.append(symbol_by_id[relation])
        return list({symbol.id: symbol for symbol in symbols}.values())

    @staticmethod
    def _routes_for_items(items: list[SemanticMemoryItem], code: RepositoryCodeIntelligence, message: str) -> list[RouteEndpoint]:
        route_by_id = {route.id: route for route in code.routes}
        selected = []
        for item in items:
            if item.route and item.route in route_by_id:
                selected.append(route_by_id[item.route])
        lower = message.lower()
        for route in code.routes:
            if route.path.lower() in lower or route.method.lower() in lower:
                selected.append(route)
        return list({route.id: route for route in selected}.values())

    @staticmethod
    def _intent_boosts(message: str) -> dict[str, float]:
        lower = message.lower()
        boosts: dict[str, float] = {}
        if any(term in lower for term in ("auth", "login", "session", "jwt", "token", "protected", "permission", "role")):
            boosts.update({"auth": 0.55, "route": 0.25, "symbol": 0.15})
        if any(term in lower for term in ("api", "route", "endpoint", "controller")):
            boosts.update({"route": 0.55, "symbol": 0.2})
        if any(term in lower for term in ("state", "store", "redux", "zustand", "provider", "hook", "query")):
            boosts.update({"state": 0.55, "symbol": 0.25})
        if any(term in lower for term in ("deploy", "runtime", "architecture", "topology")):
            boosts.update({"architecture": 0.35, "deployment": 0.45, "entrypoint": 0.25})
        if any(term in lower for term in ("env", "environment", "secret", "config")):
            boosts.update({"environment": 0.5, "deployment": 0.2})
        return boosts

    @staticmethod
    def _term_counts(text: str) -> Counter[str]:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_]{1,}", text)
        expanded: list[str] = []
        for word in words:
            expanded.append(word.lower())
            expanded.extend(part.lower() for part in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)|\d+", word))
        return Counter(word for word in expanded if word and word not in STOP_WORDS)

    @staticmethod
    def _cosine(left: Counter[str], right: Counter[str]) -> float:
        if not left or not right:
            return 0.0
        shared = set(left) & set(right)
        numerator = sum(left[token] * right[token] for token in shared)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _matches_query(needles: list[str], values: list[str]) -> bool:
        text = " ".join(values).lower()
        return any(needle in text for needle in needles)
