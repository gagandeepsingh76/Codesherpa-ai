from __future__ import annotations

import ast
import json
import math
import posixpath
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from backend.models import ArchitectureEdge, ArchitectureMap, ArchitectureNode, Confidence, RepositoryScan


SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
JS_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
PYTHON_EXTENSIONS = {".py"}
STYLE_EXTENSIONS = {".css", ".scss", ".sass", ".html", ".md", ".mdx"}
ASSET_EXTENSIONS = {
    ".avif",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
}
JS_RESOLVE_EXTENSIONS = JS_EXTENSIONS | STYLE_EXTENSIONS | ASSET_EXTENSIONS | {".json"}
ASSET_DIRS = {"public", "asset", "assets", "image", "images", "img", "static", "media"}
DEPLOYMENT_FILES = {
    ".github",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "render.yaml",
    "render.yml",
    "vercel.json",
    "workflows",
}
MANIFEST_NAMES = {
    "package.json",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "tsconfig.json",
    "tsconfig.base.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "vite.config.js",
    "vite.config.mjs",
    "vite.config.ts",
    "tailwind.config.js",
    "tailwind.config.mjs",
    "tailwind.config.ts",
    "go.mod",
    "Cargo.toml",
    "schema.prisma",
}


@dataclass(frozen=True)
class ImportSpec:
    specifier: str
    kind: str
    imported_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedFile:
    imports: tuple[ImportSpec, ...] = ()
    asset_refs: tuple[str, ...] = ()
    framework_signals: tuple[str, ...] = ()
    entrypoint_signals: tuple[str, ...] = ()


@dataclass
class EdgeEvidence:
    source: str
    target: str
    label: str
    kind: str
    weight: float = 0.0
    confidence: Confidence = "medium"
    reasons: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def add(self, amount: float, reason: str, file: str | None = None, confidence: Confidence | None = None) -> None:
        self.weight += amount
        if reason not in self.reasons:
            self.reasons.append(reason)
        if file and file not in self.files:
            self.files.append(file)
        if confidence == "high" or (confidence == "medium" and self.confidence == "low"):
            self.confidence = confidence


@dataclass
class NodeEvidence:
    id: str
    label: str
    type: str
    role: str
    description: str
    confidence: Confidence
    framework: str | None = None
    entrypoint: bool = False
    dependency_count: int = 0
    ownership_score: float = 0.0
    runtime_classification: str | None = None
    group: str | None = None
    file_count: int = 0
    files: set[str] = field(default_factory=set)
    signals: list[str] = field(default_factory=list)
    x: float | None = None
    y: float | None = None


class RepositoryDependencyGraph:
    _parse_cache: dict[tuple[str, int, int], ParsedFile] = {}

    def analyze(self, scan: RepositoryScan) -> ArchitectureMap:
        repo_path = Path(scan.path)
        file_set = set(scan.files)
        source_files = [
            file
            for file in scan.files
            if Path(file).suffix.lower() in SOURCE_EXTENSIONS | STYLE_EXTENSIONS
        ]
        parsed = self._parse_files(repo_path, source_files)
        aliases = self._tsconfig_aliases(scan)
        python_modules = self._python_module_index(scan.files)

        node_ids = self._initial_node_ids(scan)
        edges: dict[tuple[str, str, str], EdgeEvidence] = {}
        file_dependencies: list[dict[str, Any]] = []
        metrics = {
            "source_files_analyzed": len(source_files),
            "imports_detected": 0,
            "imports_resolved": 0,
            "asset_references": 0,
            "external_imports": 0,
            "semantic_edges": 0,
            "internal_import_edges": 0,
            "internal_import_traces": 0,
        }

        for file, parsed_file in parsed.items():
            source_node = self._node_id_for_file(file, scan)
            node_ids.add(source_node)
            for import_spec in parsed_file.imports:
                metrics["imports_detected"] += 1
                target = self._resolve_import(file, import_spec, repo_path, file_set, aliases, python_modules)
                if target:
                    metrics["imports_resolved"] += 1
                    target_node = self._node_id_for_file(target, scan)
                    node_ids.add(target_node)
                    if source_node != target_node:
                        label = self._edge_label(source_node, target_node, import_spec.kind)
                        reason = f"{file} {import_spec.kind} `{import_spec.specifier}`"
                        self._add_edge(edges, source_node, target_node, label, "import", 1.0, reason, file, "high")
                    file_dependencies.append(
                        {
                            "source_file": file,
                            "target_file": target,
                            "source_node": source_node,
                            "target_node": target_node,
                            "specifier": import_spec.specifier,
                            "kind": import_spec.kind,
                            "statement": f"{import_spec.kind} `{import_spec.specifier}`",
                        }
                    )
                else:
                    metrics["external_imports"] += 1

            for asset_ref in parsed_file.asset_refs:
                asset_node = self._resolve_asset_node(file, asset_ref, repo_path, file_set, scan)
                if not asset_node:
                    continue
                metrics["asset_references"] += 1
                node_ids.add(asset_node)
                reason = f"{file} references static asset `{asset_ref}`"
                if asset_node != source_node:
                    self._add_edge(edges, asset_node, source_node, "assets for", "asset", 1.0, reason, file, "high")
                    file_dependencies.append(
                        {
                            "source_file": asset_ref,
                            "target_file": file,
                            "source_node": asset_node,
                            "target_node": source_node,
                            "specifier": asset_ref,
                            "kind": "asset",
                            "statement": f"asset reference `{asset_ref}`",
                        }
                    )

        internal_edges, internal_traces = self._add_internal_import_edges(scan, node_ids, edges, file_dependencies)
        metrics["internal_import_edges"] = internal_edges
        metrics["internal_import_traces"] = internal_traces
        metrics["semantic_edges"] += self._add_semantic_edges(scan, node_ids, edges, parsed)
        nodes = self._build_nodes(scan, node_ids, edges, parsed)
        self._stabilize_layout(nodes, edges)
        edge_models = self._edge_models(edges, {node.id for node in nodes}, file_dependencies)
        connected_ratio = self._connected_ratio(nodes, edge_models)
        metrics.update(
            {
                "nodes": len(nodes),
                "edges": len(edge_models),
                "connected_ratio": round(connected_ratio, 3),
                "import_trace_density": round(metrics["imports_resolved"] / max(1, len(source_files)), 3),
            }
        )

        framework_signals = self._framework_signals(scan)
        confidence = self._confidence(scan, metrics, framework_signals)
        file_graph = self._file_graph(scan, nodes, file_dependencies)
        risk_analysis = self._risk_analysis(scan, nodes, edge_models, file_dependencies)
        hotspots = self._hotspots(nodes, edge_models, risk_analysis)
        topology = self._topology(scan, nodes, edge_models, file_dependencies)
        evolution = self._evolution(scan)
        return ArchitectureMap(
            summary=self._summary(scan, nodes, edge_models, metrics),
            boundaries=self._boundaries(scan, nodes, edge_models),
            nodes=nodes,
            edges=edge_models,
            dependency_flow=self._dependency_flow(scan, nodes, edge_models, metrics),
            confidence=confidence,
            framework_signals=framework_signals,
            graph_metrics=metrics,
            file_graph=file_graph,
            risk_analysis=risk_analysis,
            hotspots=hotspots,
            topology=topology,
            evolution=evolution,
        )

    def _parse_files(self, repo_path: Path, files: list[str]) -> dict[str, ParsedFile]:
        if not files:
            return {}

        def parse_one(file: str) -> tuple[str, ParsedFile]:
            return file, self._parse_file(repo_path, file)

        max_workers = min(8, max(1, len(files)))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            return dict(pool.map(parse_one, files))

    def _parse_file(self, repo_path: Path, file: str) -> ParsedFile:
        path = repo_path / file
        try:
            stat = path.stat()
        except OSError:
            return ParsedFile()
        cache_key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        cached = self._parse_cache.get(cache_key)
        if cached:
            return cached

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ParsedFile()

        suffix = Path(file).suffix.lower()
        if suffix in PYTHON_EXTENSIONS:
            parsed = self._parse_python(text, file)
        elif suffix in JS_EXTENSIONS:
            parsed = self._parse_js(text, file)
        else:
            parsed = ParsedFile(asset_refs=tuple(self._asset_refs(text)))
        self._parse_cache[cache_key] = parsed
        return parsed

    @staticmethod
    def _parse_python(text: str, file: str) -> ParsedFile:
        imports: list[ImportSpec] = []
        framework_signals: list[str] = []
        entrypoint_signals: list[str] = []
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return ParsedFile(asset_refs=tuple(RepositoryDependencyGraph._asset_refs(text)))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportSpec(alias.name, "python import"))
            elif isinstance(node, ast.ImportFrom):
                names = tuple(alias.name for alias in node.names if alias.name != "*")
                prefix = "." * node.level
                imports.append(ImportSpec(f"{prefix}{node.module or ''}", "python import", names))

            if isinstance(node, ast.Call):
                name = RepositoryDependencyGraph._call_name(node.func)
                if name in {"FastAPI", "fastapi.FastAPI"}:
                    framework_signals.append(f"FastAPI app factory in {file}")
                    entrypoint_signals.append("FastAPI application")
                elif name in {"Django", "django"}:
                    framework_signals.append(f"Django runtime signal in {file}")

        return ParsedFile(
            imports=tuple(imports),
            asset_refs=tuple(RepositoryDependencyGraph._asset_refs(text)),
            framework_signals=tuple(dict.fromkeys(framework_signals)),
            entrypoint_signals=tuple(dict.fromkeys(entrypoint_signals)),
        )

    @staticmethod
    def _parse_js(text: str, file: str) -> ParsedFile:
        imports: list[ImportSpec] = []
        framework_signals: list[str] = []
        entrypoint_signals: list[str] = []

        static_pattern = re.compile(
            r"(?:import|export)\s+(?:type\s+)?(?:[^;]*?\s+from\s*)?[\"']([^\"']+)[\"']",
            re.MULTILINE,
        )
        dynamic_pattern = re.compile(r"\bimport\s*\(\s*[\"']([^\"']+)[\"']\s*\)")
        require_pattern = re.compile(r"\brequire\s*\(\s*[\"']([^\"']+)[\"']\s*\)")

        for match in static_pattern.finditer(text):
            statement = match.group(0)
            specifier = match.group(1)
            kind = "barrel export" if statement.lstrip().startswith("export") else "static import"
            imports.append(ImportSpec(specifier, kind))
        for match in dynamic_pattern.finditer(text):
            imports.append(ImportSpec(match.group(1), "dynamic import"))
        for match in require_pattern.finditer(text):
            imports.append(ImportSpec(match.group(1), "require"))

        if re.search(r"\bfrom\s+[\"']react[\"']|\brequire\([\"']react[\"']\)", text):
            framework_signals.append(f"React import in {file}")
        if re.search(r"\bNextResponse\b|\bnext/(?:server|navigation|link|image)\b", text):
            framework_signals.append(f"Next.js runtime import in {file}")
        if re.search(r"\bNestFactory\b|@nestjs/", text):
            framework_signals.append(f"NestJS runtime signal in {file}")
        if re.search(r"\bexpress\s*\(", text):
            framework_signals.append(f"Express app factory in {file}")
        if PurePosixPath(file).name in {"page.tsx", "layout.tsx", "route.ts", "route.js", "main.tsx", "main.ts", "index.tsx"}:
            entrypoint_signals.append("frontend/runtime entrypoint")

        asset_refs = list(RepositoryDependencyGraph._asset_refs(text))
        for import_spec in imports:
            if Path(import_spec.specifier).suffix.lower() in ASSET_EXTENSIONS:
                asset_refs.append(import_spec.specifier)

        return ParsedFile(
            imports=tuple(dict.fromkeys(imports)),
            asset_refs=tuple(dict.fromkeys(asset_refs)),
            framework_signals=tuple(dict.fromkeys(framework_signals)),
            entrypoint_signals=tuple(dict.fromkeys(entrypoint_signals)),
        )

    @staticmethod
    def _call_name(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{RepositoryDependencyGraph._call_name(node.value)}.{node.attr}"
        return ""

    @staticmethod
    def _asset_refs(text: str) -> list[str]:
        extensions = "|".join(re.escape(ext.lstrip(".")) for ext in sorted(ASSET_EXTENSIONS))
        patterns = [
            rf"[\"'`]([^\"'`]+\.({extensions})(?:\?[^\"'`]*)?)[\"'`]",
            rf"url\(\s*[\"']?([^\"')]+\.({extensions})(?:\?[^\"')]+)?)",
        ]
        refs: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                refs.append(match.group(1))
        return refs[:40]

    @staticmethod
    def _python_module_index(files: list[str]) -> dict[str, str]:
        index: dict[str, str] = {}
        for file in files:
            if Path(file).suffix.lower() != ".py":
                continue
            path = PurePosixPath(file)
            parts = list(path.with_suffix("").parts)
            if parts[-1] == "__init__":
                parts = parts[:-1]
            if not parts:
                continue
            for start in range(min(2, len(parts))):
                key = ".".join(parts[start:])
                index.setdefault(key, file)
        return index

    @staticmethod
    def _tsconfig_aliases(scan: RepositoryScan) -> list[tuple[str, list[str], str, str]]:
        aliases: list[tuple[str, list[str], str, str]] = []
        for file, manifest in scan.manifests.items():
            name = PurePosixPath(file).name
            if not name.startswith("tsconfig") or not isinstance(manifest, dict):
                continue
            compiler_options = manifest.get("compilerOptions") or {}
            if not isinstance(compiler_options, dict):
                continue
            base_dir = PurePosixPath(file).parent.as_posix()
            if base_dir == ".":
                base_dir = ""
            base_url = str(compiler_options.get("baseUrl") or ".")
            paths = compiler_options.get("paths") or {}
            if isinstance(paths, dict):
                for pattern, replacements in paths.items():
                    if isinstance(replacements, str):
                        replacements = [replacements]
                    if isinstance(replacements, list):
                        aliases.append((str(pattern), [str(item) for item in replacements], base_dir, base_url))
        if not aliases and "Next.js" in scan.frameworks:
            aliases.append(("@/*", ["./*"], "", "."))
        return aliases

    def _resolve_import(
        self,
        source_file: str,
        import_spec: ImportSpec,
        repo_path: Path,
        file_set: set[str],
        aliases: list[tuple[str, list[str], str, str]],
        python_modules: dict[str, str],
    ) -> str | None:
        suffix = Path(source_file).suffix.lower()
        if suffix in PYTHON_EXTENSIONS:
            return self._resolve_python_import(source_file, import_spec, python_modules, file_set)
        if suffix in JS_EXTENSIONS:
            return self._resolve_js_import(source_file, import_spec.specifier, repo_path, file_set, aliases)
        return None

    def _resolve_python_import(
        self,
        source_file: str,
        import_spec: ImportSpec,
        python_modules: dict[str, str],
        file_set: set[str],
    ) -> str | None:
        specifier = import_spec.specifier
        candidates: list[str] = []
        if specifier.startswith("."):
            level = len(specifier) - len(specifier.lstrip("."))
            module = specifier[level:]
            source_parts = list(PurePosixPath(source_file).parent.parts)
            base_parts = source_parts[: max(0, len(source_parts) - level + 1)]
            module_parts = module.split(".") if module else []
            if module_parts:
                candidates.append(".".join(base_parts + module_parts))
            for name in import_spec.imported_names:
                candidates.append(".".join(base_parts + module_parts + [name]))
        else:
            candidates.append(specifier)
            for name in import_spec.imported_names:
                candidates.append(f"{specifier}.{name}")

        for candidate in candidates:
            if candidate in python_modules:
                return python_modules[candidate]
            path = candidate.replace(".", "/")
            resolved = self._resolve_path_candidate(path, file_set, [".py"])
            if resolved:
                return resolved
        return None

    def _resolve_js_import(
        self,
        source_file: str,
        specifier: str,
        repo_path: Path,
        file_set: set[str],
        aliases: list[tuple[str, list[str], str, str]],
    ) -> str | None:
        if specifier.startswith("."):
            base = PurePosixPath(source_file).parent.joinpath(specifier).as_posix()
            return self._resolve_path_candidate(base, file_set, list(JS_RESOLVE_EXTENSIONS))

        for pattern, replacements, base_dir, base_url in aliases:
            matched = self._match_alias(pattern, specifier)
            if matched is None:
                continue
            for replacement in replacements:
                replaced = replacement.replace("*", matched)
                candidate = PurePosixPath(base_dir).joinpath(base_url, replaced).as_posix()
                resolved = self._resolve_path_candidate(candidate, file_set, list(JS_RESOLVE_EXTENSIONS))
                if resolved:
                    return resolved

        if "/" in specifier and not specifier.startswith("@"):
            resolved = self._resolve_path_candidate(specifier, file_set, list(JS_RESOLVE_EXTENSIONS))
            if resolved:
                return resolved

        package_name = specifier.split("/", 1)[0]
        if package_name.startswith("@") and "/" in specifier:
            package_name = "/".join(specifier.split("/", 2)[:2])
        package_files = [file for file in file_set if file.endswith("package.json")]
        for package_file in package_files[:80]:
            path = repo_path / package_file
            try:
                package = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            if isinstance(package, dict) and package.get("name") == package_name:
                package_dir = PurePosixPath(package_file).parent.as_posix()
                entry = package.get("source") or package.get("module") or package.get("main") or "index"
                return self._resolve_path_candidate(f"{package_dir}/{entry}", file_set, list(JS_EXTENSIONS | {".json"}))
        return None

    @staticmethod
    def _match_alias(pattern: str, specifier: str) -> str | None:
        if "*" not in pattern:
            return "" if pattern == specifier else None
        prefix, suffix = pattern.split("*", 1)
        if not specifier.startswith(prefix) or (suffix and not specifier.endswith(suffix)):
            return None
        end = len(specifier) - len(suffix) if suffix else len(specifier)
        return specifier[len(prefix):end]

    @staticmethod
    def _resolve_path_candidate(base: str, file_set: set[str], extensions: list[str]) -> str | None:
        normalized = PurePosixPath(base).as_posix().replace("\\", "/")
        while normalized.startswith("./"):
            normalized = normalized[2:]
        normalized = re.sub(r"/+", "/", normalized)
        normalized = posixpath.normpath(normalized)
        if normalized == ".":
            normalized = ""
        candidates = [normalized]
        if Path(normalized).suffix:
            candidates.append(normalized)
        else:
            candidates.extend(f"{normalized}{ext}" for ext in extensions)
            candidates.extend(f"{normalized}/index{ext}" for ext in extensions)
            candidates.extend(f"{normalized}/__init__{ext}" for ext in extensions if ext == ".py")
        for candidate in candidates:
            if candidate in file_set:
                return candidate
        return None

    def _resolve_asset_node(
        self,
        source_file: str,
        asset_ref: str,
        repo_path: Path,
        file_set: set[str],
        scan: RepositoryScan,
    ) -> str | None:
        clean = asset_ref.split("?", 1)[0].strip()
        if clean.startswith(("http://", "https://", "data:")):
            return None
        candidates: list[str] = []
        if clean.startswith("/"):
            candidates.append(f"public/{clean.lstrip('/')}")
        elif clean.startswith("."):
            candidates.append(PurePosixPath(source_file).parent.joinpath(clean).as_posix())
        else:
            candidates.append(clean)
            candidates.append(f"public/{clean.lstrip('/')}")

        for candidate in candidates:
            resolved = self._resolve_path_candidate(candidate, file_set, list(ASSET_EXTENSIONS))
            if resolved:
                return self._node_id_for_file(resolved, scan)

        asset_dirs = {file.split("/", 1)[0] for file in scan.files if file.split("/", 1)[0] in ASSET_DIRS}
        if clean.startswith("/") and "public" in asset_dirs:
            return "public"
        return None

    @staticmethod
    def _initial_node_ids(scan: RepositoryScan) -> set[str]:
        node_ids = {folder.path for folder in scan.folders[:30]}
        file_names = {PurePosixPath(file).name for file in scan.files}
        if scan.manifests:
            node_ids.add("manifest")
        for file in scan.files:
            parts = PurePosixPath(file).parts
            if not parts:
                continue
            if parts[0] in ASSET_DIRS:
                node_ids.add(parts[0])
            elif len(parts) > 1 and parts[1] in ASSET_DIRS:
                node_ids.add(f"{parts[0]}/{parts[1]}")
            if parts[0] == ".github":
                node_ids.add(".github")
            if parts[0] == "workflows":
                node_ids.add("workflows")
        for name in DEPLOYMENT_FILES:
            if name in file_names or any(file == name or file.startswith(f"{name}/") for file in scan.files):
                node_ids.add(name)
        if node_ids & DEPLOYMENT_FILES:
            node_ids.add("deployment")
        return node_ids

    @staticmethod
    def _node_id_for_file(file: str, scan: RepositoryScan) -> str:
        path = PurePosixPath(file)
        parts = path.parts
        name = path.name
        if not parts:
            return "root"
        if parts[0] == ".github":
            return ".github"
        if parts[0] == "workflows":
            return "workflows"
        if len(parts) == 1 and name in DEPLOYMENT_FILES:
            return name
        if name in MANIFEST_NAMES or name in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock"}:
            return "manifest"
        if parts[0] in ASSET_DIRS:
            return parts[0]
        if len(parts) > 1 and parts[1] in ASSET_DIRS:
            return f"{parts[0]}/{parts[1]}"
        if len(parts) == 1:
            if file in scan.entry_points or name in {"main.py", "app.py", "server.js", "server.ts"}:
                return "runtime"
            return "root"
        return parts[0]

    def _add_semantic_edges(
        self,
        scan: RepositoryScan,
        node_ids: set[str],
        edges: dict[tuple[str, str, str], EdgeEvidence],
        parsed: dict[str, ParsedFile],
    ) -> int:
        added = 0
        source_nodes = {
            self._node_id_for_file(file, scan)
            for file in scan.files
            if Path(file).suffix.lower() in SOURCE_EXTENSIONS
        }
        frontend_nodes = {
            node
            for node in source_nodes | node_ids
            if self._classify_node(node, scan)[0] == "frontend" and self._classify_node(node, scan)[1] != "static assets"
        }
        backend_nodes = {node for node in source_nodes | node_ids if self._classify_node(node, scan)[0] == "backend"}
        shared_nodes = {node for node in source_nodes | node_ids if self._classify_node(node, scan)[0] == "shared"}
        runtime_nodes = frontend_nodes | backend_nodes | shared_nodes

        if scan.manifests:
            node_ids.add("manifest")
            for node in sorted(runtime_nodes)[:20]:
                if node != "manifest":
                    self._add_edge(
                        edges,
                        "manifest",
                        node,
                        "configures",
                        "manifest",
                        0.8,
                        self._manifest_reason(scan, node),
                        None,
                        "medium",
                    )
                    added += 1

        deployment_sources = {
            node for node in node_ids if node in DEPLOYMENT_FILES or node.startswith(".github")
        }
        if deployment_sources:
            node_ids.add("deployment")
            for node in sorted(deployment_sources):
                if node != "deployment":
                    self._add_edge(
                        edges,
                        node,
                        "deployment",
                        "feeds",
                        "deployment",
                        1.4,
                        f"{node} contributes deployment or CI configuration",
                        None,
                        "high" if node in {".github", "render.yaml", "vercel.json"} else "medium",
                    )
                    added += 1
            for node in sorted((frontend_nodes | backend_nodes) or runtime_nodes)[:12]:
                self._add_edge(
                    edges,
                    "deployment",
                    node,
                    "deploys",
                    "deployment",
                    1.1,
                    "Deployment configuration targets detected runtime surfaces",
                    None,
                    "medium",
                )
                added += 1

        asset_nodes = {node for node in node_ids if any(part in ASSET_DIRS for part in node.split("/"))}
        if asset_nodes and frontend_nodes:
            for asset_node in sorted(asset_nodes):
                has_edge = any(edge.source == asset_node for edge in edges.values())
                if has_edge:
                    continue
                for frontend_node in sorted(frontend_nodes)[:4]:
                    self._add_edge(
                        edges,
                        asset_node,
                        frontend_node,
                        "static assets",
                        "asset",
                        0.7,
                        f"{asset_node} is served by the detected frontend framework",
                        None,
                        "medium",
                    )
                    added += 1

        if frontend_nodes and backend_nodes:
            has_frontend_backend_edge = any(
                edge.source in frontend_nodes and edge.target in backend_nodes for edge in edges.values()
            )
            if not has_frontend_backend_edge:
                for frontend in sorted(frontend_nodes)[:4]:
                    for backend in sorted(backend_nodes)[:3]:
                        self._add_edge(
                            edges,
                            frontend,
                            backend,
                            "calls API",
                            "semantic",
                            0.6,
                            "Frontend and backend/API boundaries were both detected",
                            None,
                            "medium" if scan.entry_points else "low",
                        )
                        added += 1

        for node in sorted(frontend_nodes | backend_nodes):
            for shared in sorted(shared_nodes):
                if node == shared:
                    continue
                key_exists = any(edge.source == node and edge.target == shared for edge in edges.values())
                if not key_exists:
                    self._add_edge(
                        edges,
                        node,
                        shared,
                        "uses shared",
                        "semantic",
                        0.35,
                        "Shared source boundary detected near runtime code",
                        None,
                        "low",
                    )
                    added += 1

        test_nodes = {node for node in node_ids if self._classify_node(node, scan)[0] == "tests"}
        for test_node in sorted(test_nodes):
            for target in sorted(runtime_nodes)[:4]:
                has_edge = any(edge.source == test_node and edge.target == target for edge in edges.values())
                if test_node != target and not has_edge:
                    self._add_edge(
                        edges,
                        test_node,
                        target,
                        "validates",
                        "semantic",
                        0.6,
                        "Test folder validates nearby runtime surfaces",
                        None,
                        "medium",
                    )
                    added += 1

        doc_nodes = {node for node in node_ids if self._classify_node(node, scan)[0] == "docs"}
        for doc_node in sorted(doc_nodes):
            for target in sorted(runtime_nodes)[:3]:
                has_edge = any(edge.source == doc_node and edge.target == target for edge in edges.values())
                if doc_node != target and not has_edge:
                    self._add_edge(
                        edges,
                        doc_node,
                        target,
                        "explains",
                        "semantic",
                        0.4,
                        "Documentation is connected to primary runtime surfaces",
                        None,
                        "medium",
                    )
                    added += 1

        for file, parsed_file in parsed.items():
            node = self._node_id_for_file(file, scan)
            if parsed_file.entrypoint_signals:
                node_ids.add(node)
        return added

    def _add_internal_import_edges(
        self,
        scan: RepositoryScan,
        node_ids: set[str],
        edges: dict[tuple[str, str, str], EdgeEvidence],
        file_dependencies: list[dict[str, Any]],
    ) -> tuple[int, int]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        trace_count = 0
        for dependency in file_dependencies:
            if dependency.get("kind") == "asset":
                continue
            if dependency.get("source_node") != dependency.get("target_node"):
                continue
            source_file = str(dependency.get("source_file", ""))
            target_file = str(dependency.get("target_file", ""))
            parent = str(dependency.get("source_node", ""))
            source_child = self._promoted_internal_node(parent, source_file, scan)
            target_child = self._promoted_internal_node(parent, target_file, scan)
            if not source_child or not target_child or source_child == target_child:
                continue
            trace_count += 1
            key = (source_child, target_child)
            edge = grouped.setdefault(key, {"weight": 0.0, "reasons": [], "files": [], "parent": parent})
            edge["weight"] += 1.0
            statement = str(dependency.get("statement") or dependency.get("specifier") or "internal import")
            if statement not in edge["reasons"]:
                edge["reasons"].append(statement)
            if source_file and source_file not in edge["files"]:
                edge["files"].append(source_file)

        added = 0
        for (source_child, target_child), payload in sorted(grouped.items(), key=lambda item: (-item[1]["weight"], item[0]))[:96]:
            node_ids.add(source_child)
            node_ids.add(target_child)
            reason = f"Internal import relationship inside {payload['parent']}: " + "; ".join(payload["reasons"][:3])
            self._add_edge(
                edges,
                source_child,
                target_child,
                "imports internal",
                "import",
                float(payload["weight"]),
                reason,
                payload["files"][0] if payload["files"] else None,
                "high",
            )
            added += 1
        return added, trace_count

    @staticmethod
    def _promoted_internal_node(parent: str, file: str, scan: RepositoryScan) -> str | None:
        if not file or not parent or parent in {"manifest", "deployment"}:
            return None
        path = PurePosixPath(file)
        parts = path.parts
        if not parts:
            return None
        parent_parts = PurePosixPath(parent).parts
        if parent == "root":
            return f"root/{path.name}"
        if parent == "runtime":
            return f"runtime/{path.name}"
        if not file.startswith(f"{parent}/") and RepositoryDependencyGraph._node_id_for_file(file, scan) != parent:
            return None
        relative_parts = parts[len(parent_parts):] if file.startswith(f"{parent}/") else parts
        if not relative_parts:
            return None
        if len(relative_parts) >= 2:
            return f"{parent}/{relative_parts[0]}"
        return f"{parent}/{relative_parts[0]}"

    @staticmethod
    def _manifest_reason(scan: RepositoryScan, node: str) -> str:
        frameworks = ", ".join(scan.frameworks[:4]) if scan.frameworks else "runtime dependencies"
        return f"Detected manifests declare {frameworks} used by {node}"

    @staticmethod
    def _add_edge(
        edges: dict[tuple[str, str, str], EdgeEvidence],
        source: str,
        target: str,
        label: str,
        kind: str,
        weight: float,
        reason: str,
        file: str | None,
        confidence: Confidence,
    ) -> None:
        if source == target:
            return
        key = (source, target, kind)
        edge = edges.get(key)
        if not edge:
            edge = EdgeEvidence(source=source, target=target, label=label, kind=kind, confidence=confidence)
            edges[key] = edge
        edge.add(weight, reason, file, confidence)

    @staticmethod
    def _edge_label(source: str, target: str, kind: str) -> str:
        source_lower = source.lower()
        target_lower = target.lower()
        if "test" in source_lower:
            return "validates"
        if kind == "barrel export":
            return "re-exports"
        if kind == "dynamic import":
            return "loads"
        if "frontend" in source_lower and "backend" in target_lower:
            return "calls"
        return "imports"

    def _build_nodes(
        self,
        scan: RepositoryScan,
        node_ids: set[str],
        edges: dict[tuple[str, str, str], EdgeEvidence],
        parsed: dict[str, ParsedFile],
    ) -> list[ArchitectureNode]:
        folder_counts = Counter(self._node_id_for_file(file, scan) for file in scan.files)
        dependency_counts = Counter()
        incoming_counts = Counter()
        connected_ids: set[str] = set()
        for edge in edges.values():
            dependency_counts[edge.source] += edge.weight
            incoming_counts[edge.target] += edge.weight
            connected_ids.add(edge.source)
            connected_ids.add(edge.target)
        entrypoint_nodes = {self._node_id_for_file(file, scan) for file in scan.entry_points}
        for file, parsed_file in parsed.items():
            if parsed_file.entrypoint_signals:
                entrypoint_nodes.add(self._node_id_for_file(file, scan))

        node_models: list[ArchitectureNode] = []
        for node_id in sorted(node_ids):
            if (
                node_id not in connected_ids
                and node_id not in entrypoint_nodes
                and node_id not in {"deployment", "manifest"}
                and not any(part in ASSET_DIRS for part in node_id.lower().split("/"))
            ):
                continue
            node_type, role, description, confidence = self._classify_node(node_id, scan)
            framework = self._node_framework(node_id, scan)
            dependency_count = int(dependency_counts[node_id] + incoming_counts[node_id])
            file_count = folder_counts[node_id] or len(self._files_for_node(node_id, scan))
            ownership_score = min(1.0, (file_count / max(1, len(scan.files))) + (dependency_count / max(4, len(edges))))
            runtime_classification = self._runtime_classification(node_id, node_type, scan)
            signals = self._node_signals(node_id, scan, parsed)
            node_models.append(
                ArchitectureNode(
                    id=node_id,
                    label=node_id,
                    type=node_type,  # type: ignore[arg-type]
                    description=description,
                    confidence=confidence,
                    role=role,
                    framework=framework,
                    entrypoint=node_id in entrypoint_nodes,
                    dependency_count=dependency_count,
                    ownership_score=round(ownership_score, 3),
                    runtime_classification=runtime_classification,
                    group=self._group_for_type(node_type),
                    metadata={
                        "file_count": file_count,
                        "signals": signals[:8],
                        "outgoing_weight": round(dependency_counts[node_id], 2),
                        "incoming_weight": round(incoming_counts[node_id], 2),
                    },
                )
            )

        node_models.sort(key=lambda node: (node.id not in {"deployment", "manifest"}, -node.dependency_count, node.id))
        return node_models[:36]

    @staticmethod
    def _classify_node(node_id: str, scan: RepositoryScan) -> tuple[str, str, str, Confidence]:
        normalized = node_id.lower()
        root = normalized.split("/", 1)[0]
        folder = next((folder for folder in scan.folders if folder.path == node_id), None)
        if node_id == "manifest":
            return "config", "dependency manifest", "Dependency, framework, and runtime configuration.", "high"
        if node_id == "deployment":
            return "infra", "deployment pipeline", "CI/CD and hosting flow inferred from deployment manifests.", "high"
        if node_id in DEPLOYMENT_FILES or normalized.startswith(".github"):
            return "infra", "deployment config", "Automation, CI, container, or hosting configuration.", "high"
        if any(part in ASSET_DIRS for part in normalized.split("/")):
            return "frontend", "static assets", "Static media and public assets consumed by UI/runtime surfaces.", "medium"
        if normalized in {"app", "pages", "components", "frontend", "client", "web"}:
            return "frontend", "frontend runtime", "Application routes, pages, or UI components.", "high" if "Next.js" in scan.frameworks or "React" in scan.frameworks else "medium"
        if normalized in {"api", "server", "backend"}:
            return "backend", "backend runtime", "API, service, or request handling boundary.", "high" if any(fw in scan.frameworks for fw in {"FastAPI", "Express", "NestJS", "Django"}) else "medium"
        if root in {"api", "server", "backend"}:
            if any(part in normalized for part in ("model", "schema", "prisma", "database", "db")):
                return "data", "data layer", "Models, schemas, or persistence-related implementation.", "medium"
            if any(part in normalized for part in ("route", "controller", "middleware")):
                return "backend", "api module", "Request routing, controllers, or middleware inside the backend boundary.", "high"
            if "service" in normalized:
                return "backend", "service module", "Backend service logic inside the server runtime boundary.", "medium"
            return "backend", "backend module", "Nested backend implementation area promoted from import relationships.", "medium"
        if normalized == "src" and any(framework in scan.frameworks for framework in {"React", "Vite", "Next.js"}):
            return "frontend", "frontend runtime", "Application source tree for the detected frontend framework.", "high"
        if root in {"app", "pages", "components", "frontend", "client", "web"}:
            return "frontend", "frontend module", "Nested frontend route, component, or UI runtime area.", "medium"
        if root == "src" and any(framework in scan.frameworks for framework in {"React", "Vite", "Next.js"}):
            return "frontend", "frontend module", "Nested frontend implementation area promoted from import relationships.", "medium"
        if normalized in {"src", "lib", "packages", "shared", "common", "utils"}:
            return "shared", "shared library", "Reusable implementation or package internals.", "medium"
        if root in {"lib", "packages", "shared", "common", "utils"}:
            return "shared", "shared module", "Nested reusable implementation area promoted from import relationships.", "medium"
        if folder:
            node_type = folder.role if folder.role in {"frontend", "backend", "shared", "data", "infra", "docs", "tests"} else "package"
            return node_type, folder.role, folder.description, folder.confidence
        if normalized in {"tests", "test", "__tests__"}:
            return "tests", "test suite", "Automated tests and validation assets.", "high"
        if normalized in {"docs", "documentation"}:
            return "docs", "documentation", "Documentation and contributor learning surface.", "high"
        if normalized == "runtime":
            return "backend", "runtime entrypoint", "Root-level executable application entry point.", "medium"
        return "package", "feature module", "Repository package, feature, or implementation area.", "medium"

    @staticmethod
    def _node_framework(node_id: str, scan: RepositoryScan) -> str | None:
        node_type, _, _, _ = RepositoryDependencyGraph._classify_node(node_id, scan)
        frameworks = set(scan.frameworks)
        if node_type == "frontend":
            for framework in ("Next.js App Router", "Next.js", "React", "Vite", "Tailwind CSS"):
                if framework in frameworks:
                    return framework
        if node_type == "backend":
            for framework in ("FastAPI", "Express", "NestJS", "Django", "Flask"):
                if framework in frameworks:
                    return framework
        if node_type == "data":
            for framework in ("Prisma", "SQLAlchemy", "Drizzle ORM"):
                if framework in frameworks:
                    return framework
        return None

    @staticmethod
    def _runtime_classification(node_id: str, node_type: str, scan: RepositoryScan) -> str:
        if node_id == "deployment" or node_type == "infra":
            return "deployment"
        if node_type == "frontend":
            return "client/runtime"
        if node_type == "backend":
            return "server/runtime"
        if node_type == "shared":
            return "library"
        if node_type == "tests":
            return "validation"
        if node_type == "docs":
            return "knowledge"
        if node_type == "config":
            return "configuration"
        return "feature"

    @staticmethod
    def _group_for_type(node_type: str) -> str:
        return {
            "frontend": "frontend",
            "backend": "backend",
            "infra": "infrastructure",
            "shared": "shared",
            "tests": "testing",
            "docs": "docs",
            "data": "backend",
            "config": "infrastructure",
        }.get(node_type, "shared")

    def _node_signals(self, node_id: str, scan: RepositoryScan, parsed: dict[str, ParsedFile]) -> list[str]:
        signals: list[str] = []
        for file in scan.entry_points:
            if self._node_id_for_file(file, scan) == node_id:
                signals.append(f"entrypoint: {file}")
        for file, parsed_file in parsed.items():
            if self._node_id_for_file(file, scan) != node_id:
                continue
            signals.extend(parsed_file.framework_signals)
            signals.extend(parsed_file.entrypoint_signals)
        if node_id == "manifest":
            signals.extend(sorted(scan.manifests)[:5])
        return list(dict.fromkeys(signals))

    def _edge_models(
        self,
        edges: dict[tuple[str, str, str], EdgeEvidence],
        node_ids: set[str],
        file_dependencies: list[dict[str, Any]],
    ) -> list[ArchitectureEdge]:
        models: list[ArchitectureEdge] = []
        for edge in sorted(edges.values(), key=lambda item: (-item.weight, item.source, item.target)):
            if edge.source not in node_ids or edge.target not in node_ids:
                continue
            label = edge.label
            if edge.kind == "import" and edge.weight >= 2:
                label = f"{edge.label} ({int(edge.weight)})"
            traces = [
                {
                    "source_file": item["source_file"],
                    "target_file": item["target_file"],
                    "statement": item["statement"],
                    "specifier": item["specifier"],
                    "kind": item["kind"],
                }
                for item in file_dependencies
                if item.get("source_node") == edge.source and item.get("target_node") == edge.target
            ][:12]
            models.append(
                ArchitectureEdge(
                    source=edge.source,
                    target=edge.target,
                    label=label,
                    confidence=edge.confidence,
                    weight=round(edge.weight, 2),
                    kind=edge.kind,
                    reasons=edge.reasons[:6],
                    files=edge.files[:8],
                    metadata={
                        "reason_count": len(edge.reasons),
                        "import_traces": traces,
                        "runtime_classification": self._edge_runtime_classification(edge),
                    },
                )
            )
        return models[:80]

    @staticmethod
    def _edge_runtime_classification(edge: EdgeEvidence) -> str:
        if edge.kind == "deployment":
            return "deployment/runtime"
        if edge.kind == "asset":
            return "static asset flow"
        if edge.kind == "manifest":
            return "configuration dependency"
        if edge.kind == "import":
            return "code import dependency"
        return "semantic architecture inference"

    def _file_graph(
        self,
        scan: RepositoryScan,
        nodes: list[ArchitectureNode],
        file_dependencies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        node_ids = {node.id for node in nodes}
        expansions: dict[str, dict[str, Any]] = {}
        for node in nodes:
            files = self._files_for_node(node.id, scan)[:240]
            children = self._child_nodes_for_expansion(node.id, files, scan)
            child_ids = {child["id"] for child in children}
            child_edges: dict[tuple[str, str], dict[str, Any]] = {}
            for dependency in file_dependencies:
                if dependency.get("source_node") != node.id or dependency.get("target_node") != node.id:
                    continue
                source_child = self._child_id_for_file(node.id, str(dependency.get("source_file", "")), scan)
                target_child = self._child_id_for_file(node.id, str(dependency.get("target_file", "")), scan)
                if not source_child or not target_child or source_child == target_child:
                    continue
                if source_child not in child_ids or target_child not in child_ids:
                    continue
                key = (source_child, target_child)
                edge = child_edges.setdefault(
                    key,
                    {
                        "source": source_child,
                        "target": target_child,
                        "weight": 0,
                        "kind": dependency.get("kind", "import"),
                        "reasons": [],
                        "files": [],
                    },
                )
                edge["weight"] += 1
                statement = dependency.get("statement")
                if statement and statement not in edge["reasons"]:
                    edge["reasons"].append(statement)
                source_file = dependency.get("source_file")
                if source_file and source_file not in edge["files"]:
                    edge["files"].append(source_file)

            expansions[node.id] = {
                "parent": node.id,
                "label": node.label,
                "lazy": len(files) > len(children),
                "total_files": len(self._files_for_node(node.id, scan)),
                "nodes": children[:64],
                "edges": list(child_edges.values())[:96],
                "explanation": self._node_explanation(node, scan),
            }

        return {
            "version": 2,
            "mode": "lazy-expansion",
            "max_initial_nodes": 64,
            "expandable_nodes": [node.id for node in nodes if node.id in node_ids],
            "expansions": expansions,
        }

    def _files_for_node(self, node_id: str, scan: RepositoryScan) -> list[str]:
        if node_id == "manifest":
            return sorted(scan.manifests)
        if node_id == "deployment":
            return sorted(
                file
                for file in scan.files
                if PurePosixPath(file).parts[:1] in [(source, ) for source in DEPLOYMENT_FILES]
                or PurePosixPath(file).name in DEPLOYMENT_FILES
                or file.startswith(".github/")
                or file.startswith("workflows/")
            )
        if node_id == "root":
            return sorted(file for file in scan.files if "/" not in file)
        return sorted(file for file in scan.files if file == node_id or file.startswith(f"{node_id}/") or self._node_id_for_file(file, scan) == node_id)

    def _child_nodes_for_expansion(self, node_id: str, files: list[str], scan: RepositoryScan) -> list[dict[str, Any]]:
        counts: Counter[str] = Counter()
        samples: defaultdict[str, list[str]] = defaultdict(list)
        for file in files:
            child_id = self._child_id_for_file(node_id, file, scan)
            if not child_id:
                continue
            counts[child_id] += 1
            if len(samples[child_id]) < 5:
                samples[child_id].append(file)

        children: list[dict[str, Any]] = []
        for child_id, file_count in counts.most_common(64):
            child_label = child_id.rsplit("/", 1)[-1]
            child_type, role, _, confidence = self._classify_node(child_id.split("/", 1)[0], scan)
            if "." in child_label and file_count == 1:
                role = "file"
                child_type = self._type_for_file(samples[child_id][0], scan)
            children.append(
                {
                    "id": child_id,
                    "label": child_label,
                    "type": child_type,
                    "role": role,
                    "file_count": file_count,
                    "confidence": confidence,
                    "files": samples[child_id],
                    "framework": self._node_framework(node_id, scan),
                    "entrypoint": any(file in scan.entry_points for file in samples[child_id]),
                }
            )
        return children

    def _child_id_for_file(self, node_id: str, file: str, scan: RepositoryScan) -> str | None:
        if not file or file.startswith(("http://", "https://")):
            return None
        if node_id == "manifest":
            return f"manifest/{PurePosixPath(file).name}"
        if node_id == "deployment":
            parts = PurePosixPath(file).parts
            if parts and parts[0] in {".github", "workflows"}:
                return "/".join(parts[:2]) if len(parts) > 1 else parts[0]
            return f"deployment/{PurePosixPath(file).name}"
        if node_id == "root":
            return f"root/{PurePosixPath(file).name}"
        path = PurePosixPath(file)
        if not (file == node_id or file.startswith(f"{node_id}/")):
            if self._node_id_for_file(file, scan) != node_id:
                return None
        relative_parts = path.parts[len(PurePosixPath(node_id).parts):] if file.startswith(f"{node_id}/") else path.parts
        if not relative_parts:
            return None
        if len(relative_parts) == 1:
            return f"{node_id}/{relative_parts[0]}"
        return f"{node_id}/{relative_parts[0]}"

    @staticmethod
    def _type_for_file(file: str, scan: RepositoryScan) -> str:
        suffix = PurePosixPath(file).suffix.lower()
        if suffix in {".tsx", ".jsx", ".css", ".scss"}:
            return "frontend"
        if suffix in {".py"}:
            return "backend" if any(framework in scan.frameworks for framework in {"FastAPI", "Django", "Flask"}) else "shared"
        if PurePosixPath(file).name in MANIFEST_NAMES:
            return "config"
        if suffix in {".md", ".mdx"}:
            return "docs"
        return "package"

    @staticmethod
    def _node_explanation(node: ArchitectureNode, scan: RepositoryScan) -> str:
        framework = f" {node.framework}" if node.framework else ""
        entry = " It is an entrypoint surface." if node.entrypoint else ""
        return (
            f"{node.label} is classified as {node.role or node.type} in the {node.group or node.type} domain."
            f"{framework} signals and dependency evidence connect it to {node.dependency_count} graph relationships.{entry}"
        )

    def _risk_analysis(
        self,
        scan: RepositoryScan,
        nodes: list[ArchitectureNode],
        edges: list[ArchitectureEdge],
        file_dependencies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        adjacency: defaultdict[str, list[str]] = defaultdict(list)
        incoming: Counter[str] = Counter()
        outgoing: Counter[str] = Counter()
        weights: Counter[str] = Counter()
        node_by_id = {node.id: node for node in nodes}
        for edge in edges:
            adjacency[edge.source].append(edge.target)
            incoming[edge.target] += 1
            outgoing[edge.source] += 1
            weights[edge.source] += edge.weight or 1
            weights[edge.target] += edge.weight or 1

        cycles = self._find_cycles(adjacency, set(node_by_id), limit=8)
        file_adjacency: defaultdict[str, list[str]] = defaultdict(list)
        file_ids: set[str] = set()
        for dependency in file_dependencies:
            if dependency.get("kind") == "asset":
                continue
            source_file = dependency.get("source_file")
            target_file = dependency.get("target_file")
            if not isinstance(source_file, str) or not isinstance(target_file, str):
                continue
            file_adjacency[source_file].append(target_file)
            file_ids.add(source_file)
            file_ids.add(target_file)
        file_cycles = self._find_cycles(file_adjacency, file_ids, limit=8)
        warnings: list[dict[str, Any]] = []
        for cycle in cycles:
            warnings.append(
                {
                    "type": "circular_dependency",
                    "severity": "high" if len(cycle) <= 3 else "medium",
                    "nodes": cycle,
                    "message": f"Circular dependency path detected: {' -> '.join(cycle)}.",
                    "recommendation": "Break the cycle by moving shared contracts into a lower-level module or introducing an API boundary.",
                }
            )
        for cycle in file_cycles:
            warnings.append(
                {
                    "type": "circular_dependency",
                    "severity": "high" if len(cycle) <= 4 else "medium",
                    "nodes": cycle,
                    "message": f"File-level circular dependency path detected: {' -> '.join(cycle)}.",
                    "recommendation": "Move shared code into a lower-level module or reverse one import direction.",
                }
            )

        degree_threshold = max(4, int(len(edges) * 0.25))
        for node in nodes:
            degree = incoming[node.id] + outgoing[node.id]
            if degree >= degree_threshold:
                warnings.append(
                    {
                        "type": "oversized_hub",
                        "severity": "medium",
                        "nodes": [node.id],
                        "message": f"{node.id} is a high-coupling hub with {degree} graph relationships.",
                        "recommendation": "Split responsibilities or document ownership boundaries before adding more dependencies.",
                    }
                )

        for edge in edges:
            source = node_by_id.get(edge.source)
            target = node_by_id.get(edge.target)
            if not source or not target:
                continue
            if edge.kind == "import" and source.type == "frontend" and target.type == "backend":
                warnings.append(
                    {
                        "type": "layering_violation",
                        "severity": "high",
                        "nodes": [edge.source, edge.target],
                        "message": f"{edge.source} imports {edge.target}; frontend should generally call backend through HTTP/API contracts.",
                        "recommendation": "Move shared types into a shared package or replace direct imports with API client boundaries.",
                    }
                )
            if edge.kind == "import" and source.type == "infra" and target.type in {"frontend", "backend"}:
                warnings.append(
                    {
                        "type": "infra_leakage",
                        "severity": "medium",
                        "nodes": [edge.source, edge.target],
                        "message": f"Infrastructure node {edge.source} imports runtime node {edge.target}.",
                        "recommendation": "Keep deployment automation declarative and avoid coupling it to application internals.",
                    }
                )

        risk_score = min(100, (len(cycles) + len(file_cycles)) * 18 + len(warnings) * 7 + sum(1 for node in nodes if node.dependency_count >= degree_threshold) * 5)
        if risk_score >= 70:
            level = "high"
        elif risk_score >= 30:
            level = "medium"
        else:
            level = "low"
        return {
            "score": risk_score,
            "level": level,
            "warnings": warnings[:14],
            "cycle_count": len(cycles) + len(file_cycles),
            "high_coupling_nodes": [
                {"id": node.id, "degree": incoming[node.id] + outgoing[node.id], "weight": round(weights[node.id], 2)}
                for node in sorted(nodes, key=lambda item: weights[item.id], reverse=True)
                if incoming[node.id] + outgoing[node.id] >= degree_threshold
            ][:8],
            "recommendations": self._risk_recommendations(warnings, scan),
        }

    @staticmethod
    def _find_cycles(adjacency: dict[str, list[str]], node_ids: set[str], limit: int = 8) -> list[list[str]]:
        cycles: list[list[str]] = []

        def visit(start: str, node: str, path: list[str]) -> None:
            if len(cycles) >= limit or len(path) > 8:
                return
            for neighbor in adjacency.get(node, []):
                if neighbor not in node_ids:
                    continue
                if neighbor == start and len(path) > 1:
                    cycle = path + [start]
                    normalized = cycle[cycle.index(min(cycle[:-1])):-1]
                    normalized.append(normalized[0])
                    if normalized not in cycles:
                        cycles.append(normalized)
                elif neighbor not in path:
                    visit(start, neighbor, path + [neighbor])

        for node in sorted(node_ids):
            visit(node, node, [node])
            if len(cycles) >= limit:
                break
        return cycles

    @staticmethod
    def _risk_recommendations(warnings: list[dict[str, Any]], scan: RepositoryScan) -> list[str]:
        recommendations = []
        warning_types = {warning["type"] for warning in warnings}
        if "circular_dependency" in warning_types:
            recommendations.append("Extract shared contracts from circular paths and enforce one-way dependency rules.")
        if "layering_violation" in warning_types:
            recommendations.append("Keep frontend/backend boundaries explicit with API clients or shared DTO packages.")
        if "oversized_hub" in warning_types:
            recommendations.append("Review high-degree hubs before onboarding contributors into those modules.")
        if "infra_leakage" in warning_types:
            recommendations.append("Separate deployment automation from runtime implementation imports.")
        if not recommendations and scan.entry_points:
            recommendations.append("Architecture risk looks controlled; keep entrypoint and dependency documentation current.")
        return recommendations[:5]

    @staticmethod
    def _hotspots(
        nodes: list[ArchitectureNode],
        edges: list[ArchitectureEdge],
        risk_analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        risk_nodes = Counter()
        for warning in risk_analysis.get("warnings", []):
            severity_weight = {"low": 1, "medium": 2, "high": 3}.get(warning.get("severity"), 1)
            for node_id in warning.get("nodes", []):
                risk_nodes[node_id] += severity_weight

        edge_pressure = Counter()
        for edge in edges:
            edge_pressure[edge.source] += edge.weight or 1
            edge_pressure[edge.target] += edge.weight or 1

        hotspots = []
        for node in nodes:
            file_count = 0
            if isinstance(node.metadata, dict):
                value = node.metadata.get("file_count", 0)
                file_count = value if isinstance(value, int) else 0
            pressure = edge_pressure[node.id] + node.dependency_count * 0.8 + min(20, file_count / 8) + risk_nodes[node.id] * 4
            if pressure <= 0:
                continue
            hotspots.append(
                {
                    "id": node.id,
                    "label": node.label,
                    "type": node.type,
                    "pressure": round(pressure, 2),
                    "intensity": round(min(1.0, pressure / 40), 3),
                    "risk": risk_nodes[node.id],
                    "dependency_count": node.dependency_count,
                    "file_count": file_count,
                    "reason": f"{node.label} has {node.dependency_count} dependencies, {file_count} indexed files, and {risk_nodes[node.id]} risk signals.",
                }
            )
        return sorted(hotspots, key=lambda item: item["pressure"], reverse=True)[:12]

    def _topology(
        self,
        scan: RepositoryScan,
        nodes: list[ArchitectureNode],
        edges: list[ArchitectureEdge],
        file_dependencies: list[dict[str, Any]],
    ) -> dict[str, Any]:
        workspace_roots = self._workspace_roots(scan)
        workspaces = []
        for root in workspace_roots:
            files = [file for file in scan.files if file.startswith(f"{root}/")]
            if files:
                workspaces.append(
                    {
                        "id": root,
                        "label": root,
                        "file_count": len(files),
                        "domain": self._workspace_domain(root),
                        "package_manifest": f"{root}/package.json" if f"{root}/package.json" in scan.files else None,
                    }
                )

        workspace_edges = []
        for edge in edges:
            source_root = self._workspace_for_node(edge.source, workspace_roots)
            target_root = self._workspace_for_node(edge.target, workspace_roots)
            if source_root and target_root and source_root != target_root:
                workspace_edges.append(
                    {
                        "source": source_root,
                        "target": target_root,
                        "weight": edge.weight,
                        "kind": edge.kind,
                        "reason": edge.reasons[:2],
                    }
                )

        return {
            "monorepo": bool(workspaces) or any(manager in scan.package_managers for manager in {"pnpm", "Yarn"}),
            "workspace_roots": workspace_roots,
            "workspaces": workspaces[:40],
            "workspace_edges": workspace_edges[:80],
            "domains": self._ownership_domains(nodes),
            "framework_analyzers": self._framework_analyzers(scan),
            "critical_chains": self._critical_chains(edges),
            "dependency_sample": file_dependencies[:60],
        }

    @staticmethod
    def _workspace_roots(scan: RepositoryScan) -> list[str]:
        roots = set()
        for file in scan.files:
            parts = PurePosixPath(file).parts
            if not parts:
                continue
            if parts[0] in {"apps", "packages", "libs", "modules", "services"} and len(parts) > 1:
                roots.add("/".join(parts[:2]))
            elif PurePosixPath(file).name == "package.json" and len(parts) > 1:
                roots.add("/".join(parts[:-1]))
        package = next((manifest for path, manifest in scan.manifests.items() if PurePosixPath(path).name == "package.json" and isinstance(manifest, dict)), None)
        if isinstance(package, dict):
            workspaces = package.get("workspaces")
            if isinstance(workspaces, list):
                for pattern in workspaces:
                    if isinstance(pattern, str):
                        roots.add(pattern.rstrip("/*"))
            elif isinstance(workspaces, dict) and isinstance(workspaces.get("packages"), list):
                for pattern in workspaces["packages"]:
                    if isinstance(pattern, str):
                        roots.add(pattern.rstrip("/*"))
        return sorted(root for root in roots if root and root != ".")[:60]

    @staticmethod
    def _workspace_domain(root: str) -> str:
        first = root.split("/", 1)[0]
        return {
            "apps": "application",
            "packages": "package",
            "libs": "library",
            "services": "service",
            "modules": "module",
        }.get(first, "package")

    @staticmethod
    def _workspace_for_node(node_id: str, roots: list[str]) -> str | None:
        for root in roots:
            if node_id == root or node_id.startswith(f"{root}/") or node_id == root.split("/", 1)[0]:
                return root
        return None

    @staticmethod
    def _ownership_domains(nodes: list[ArchitectureNode]) -> list[dict[str, Any]]:
        grouped: defaultdict[str, list[str]] = defaultdict(list)
        for node in nodes:
            grouped[node.group or node.type].append(node.id)
        return [
            {"domain": domain, "nodes": sorted(node_ids), "node_count": len(node_ids)}
            for domain, node_ids in sorted(grouped.items())
        ]

    @staticmethod
    def _framework_analyzers(scan: RepositoryScan) -> list[dict[str, Any]]:
        analyzers = []
        file_names = {PurePosixPath(file).name for file in scan.files}
        if "Next.js" in scan.frameworks:
            routes = [file for file in scan.files if re.search(r"(^|/)app/.+/(page|route|layout)\.(tsx|ts|jsx|js)$", file) or re.search(r"(^|/)pages/.+\.(tsx|ts|jsx|js)$", file)]
            analyzers.append({"framework": "Next.js", "routes": routes[:40], "middleware": [file for file in scan.files if PurePosixPath(file).name.startswith("middleware.")][:8]})
        if "React" in scan.frameworks:
            analyzers.append({"framework": "React", "components": [file for file in scan.files if re.search(r"(^|/)(components|src)/.+\.(tsx|jsx)$", file)][:40]})
        if "FastAPI" in scan.frameworks:
            analyzers.append({"framework": "FastAPI", "entrypoints": [file for file in scan.entry_points if file.endswith(".py")], "routers": [file for file in scan.files if "router" in file.lower() or "/api/" in file][:30]})
        if "Express" in scan.frameworks:
            analyzers.append({"framework": "Express", "servers": [file for file in scan.files if PurePosixPath(file).name in {"server.js", "server.ts", "app.js", "app.ts"}][:12]})
        if "NestJS" in scan.frameworks:
            analyzers.append({"framework": "NestJS", "modules": [file for file in scan.files if file.endswith(".module.ts")][:40], "controllers": [file for file in scan.files if file.endswith(".controller.ts")][:40]})
        if "Django" in scan.frameworks:
            analyzers.append({"framework": "Django", "settings": [file for file in scan.files if file.endswith("settings.py")][:10], "urls": [file for file in scan.files if file.endswith("urls.py")][:20]})
        if "Prisma" in scan.frameworks or "schema.prisma" in file_names:
            analyzers.append({"framework": "Prisma", "schemas": [file for file in scan.files if PurePosixPath(file).name == "schema.prisma"]})
        if "Tailwind CSS" in scan.frameworks:
            analyzers.append({"framework": "Tailwind CSS", "configs": [file for file in scan.files if PurePosixPath(file).name.startswith("tailwind.config.")]})
        if any(name in file_names for name in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}):
            analyzers.append({"framework": "Docker", "configs": [file for file in scan.files if PurePosixPath(file).name in {"Dockerfile", "docker-compose.yml", "docker-compose.yaml"}]})
        if any(file.startswith(".github/workflows/") for file in scan.files):
            analyzers.append({"framework": "GitHub Actions", "workflows": [file for file in scan.files if file.startswith(".github/workflows/")][:40]})
        return analyzers

    @staticmethod
    def _critical_chains(edges: list[ArchitectureEdge]) -> list[dict[str, Any]]:
        return [
            {
                "source": edge.source,
                "target": edge.target,
                "weight": edge.weight,
                "kind": edge.kind,
                "label": edge.label,
                "reason": edge.reasons[:2],
            }
            for edge in sorted(edges, key=lambda item: item.weight or 0, reverse=True)[:8]
        ]

    def _evolution(self, scan: RepositoryScan) -> dict[str, Any]:
        repo_path = Path(scan.path)
        try:
            from git import Repo

            repo = Repo(repo_path, search_parent_directories=False)
        except Exception:
            return {"available": False, "reason": "Git history is unavailable for this analysis checkout."}

        churn: Counter[str] = Counter()
        commits = []
        try:
            for commit in repo.iter_commits(max_count=80):
                touched = list(commit.stats.files)[:80]
                for file in touched:
                    churn[self._node_id_for_file(file.replace("\\", "/"), scan)] += 1
                commits.append(
                    {
                        "sha": commit.hexsha[:8],
                        "date": commit.committed_datetime.date().isoformat(),
                        "summary": commit.summary[:120],
                        "files_changed": len(touched),
                    }
                )
        except Exception:
            return {"available": False, "reason": "Git history could not be read safely."}

        return {
            "available": bool(commits),
            "commits_sampled": len(commits),
            "recent_commits": commits[:12],
            "churn_by_node": [{"id": node_id, "changes": count} for node_id, count in churn.most_common(12)],
            "drift_summary": "Recent commit history is summarized as module churn; compare hotspots with churn to spot architecture drift.",
        }

    @staticmethod
    def _connected_ratio(nodes: list[ArchitectureNode], edges: list[ArchitectureEdge]) -> float:
        if not nodes:
            return 0.0
        connected = {edge.source for edge in edges} | {edge.target for edge in edges}
        return len([node for node in nodes if node.id in connected]) / len(nodes)

    def _stabilize_layout(
        self,
        nodes: list[ArchitectureNode],
        edges: dict[tuple[str, str, str], EdgeEvidence],
    ) -> None:
        if not nodes:
            return
        lanes = {
            "frontend": 18.0,
            "shared": 42.0,
            "backend": 66.0,
            "infrastructure": 82.0,
            "testing": 30.0,
            "docs": 10.0,
        }
        positions: dict[str, list[float]] = {}
        groups = defaultdict(list)
        for node in nodes:
            groups[node.group or "shared"].append(node)
        for group, group_nodes in groups.items():
            x = lanes.get(group, 50.0)
            step = 74.0 / max(1, len(group_nodes))
            for index, node in enumerate(sorted(group_nodes, key=lambda item: item.id)):
                positions[node.id] = [x, 12.0 + step * index]

        for _ in range(90):
            displacements = {node.id: [0.0, 0.0] for node in nodes}
            for i, node_a in enumerate(nodes):
                ax, ay = positions[node_a.id]
                for node_b in nodes[i + 1:]:
                    bx, by = positions[node_b.id]
                    dx = ax - bx
                    dy = ay - by
                    distance = max(2.5, math.hypot(dx, dy))
                    force = 24.0 / (distance * distance)
                    displacements[node_a.id][0] += dx / distance * force
                    displacements[node_a.id][1] += dy / distance * force
                    displacements[node_b.id][0] -= dx / distance * force
                    displacements[node_b.id][1] -= dy / distance * force

            for edge in edges.values():
                if edge.source not in positions or edge.target not in positions:
                    continue
                sx, sy = positions[edge.source]
                tx, ty = positions[edge.target]
                dx = tx - sx
                dy = ty - sy
                distance = max(1.0, math.hypot(dx, dy))
                force = min(0.08, 0.01 * edge.weight)
                displacements[edge.source][0] += dx / distance * force
                displacements[edge.source][1] += dy / distance * force
                displacements[edge.target][0] -= dx / distance * force
                displacements[edge.target][1] -= dy / distance * force

            for node in nodes:
                target_x = lanes.get(node.group or "shared", 50.0)
                dx, dy = displacements[node.id]
                x, y = positions[node.id]
                x += max(-1.2, min(1.2, dx)) + (target_x - x) * 0.01
                y += max(-1.2, min(1.2, dy))
                positions[node.id] = [min(86.0, max(5.0, x)), min(86.0, max(8.0, y))]

        for node in nodes:
            x, y = positions[node.id]
            node.x = round(x, 2)
            node.y = round(y, 2)

    @staticmethod
    def _framework_signals(scan: RepositoryScan) -> list[str]:
        signals: list[str] = []
        manifest_names = {PurePosixPath(file).name for file in scan.manifests}
        for framework in scan.frameworks:
            if framework in {"Next.js", "React", "Express", "NestJS", "Vite", "Tailwind CSS", "Prisma"} and "package.json" in manifest_names:
                signals.append(f"{framework}: package manifest/config signal")
            elif framework in {"FastAPI", "Django", "Flask", "Pydantic"} and {"requirements.txt", "pyproject.toml"} & manifest_names:
                signals.append(f"{framework}: Python manifest signal")
            else:
                signals.append(f"{framework}: repository structure signal")
        if any(PurePosixPath(file).name.startswith("next.config.") for file in scan.files):
            signals.append("Next.js: next.config.* present")
        if any(PurePosixPath(file).name.startswith("vite.config.") for file in scan.files):
            signals.append("Vite: vite.config.* present")
        if any(PurePosixPath(file).name.startswith("tailwind.config.") for file in scan.files):
            signals.append("Tailwind CSS: tailwind.config.* present")
        if any(PurePosixPath(file).name == "render.yaml" for file in scan.files):
            signals.append("Render: render.yaml deployment config")
        if any(PurePosixPath(file).name == "vercel.json" for file in scan.files):
            signals.append("Vercel: vercel.json deployment config")
        return list(dict.fromkeys(signals))[:14]

    @staticmethod
    def _confidence(scan: RepositoryScan, metrics: dict[str, Any], framework_signals: list[str]) -> Confidence:
        score = 0
        score += min(30, int(metrics.get("import_trace_density", 0) * 35))
        score += 20 if framework_signals else 0
        score += 15 if scan.entry_points else 0
        score += 15 if scan.manifests else 0
        score += 10 if metrics.get("connected_ratio", 0) >= 0.75 else 0
        score += 10 if any(file in scan.files for file in ("render.yaml", "vercel.json", "docker-compose.yml")) or any(file.startswith(".github/") for file in scan.files) else 0
        if score >= 60:
            return "high"
        if score >= 35:
            return "medium"
        return "low"

    @staticmethod
    def _boundaries(scan: RepositoryScan, nodes: list[ArchitectureNode], edges: list[ArchitectureEdge]) -> list[str]:
        boundaries: list[str] = []
        node_types = {node.type for node in nodes}
        if "frontend" in node_types:
            frameworks = [fw for fw in scan.frameworks if fw in {"Next.js", "Next.js App Router", "React", "Vite", "Tailwind CSS"}]
            boundaries.append(f"Frontend boundary is backed by {', '.join(frameworks) if frameworks else 'UI folder'} signals and connected asset/runtime edges.")
        if "backend" in node_types:
            frameworks = [fw for fw in scan.frameworks if fw in {"FastAPI", "Express", "NestJS", "Django", "Flask"}]
            boundaries.append(f"Backend/API boundary is backed by {', '.join(frameworks) if frameworks else 'server/API'} signals and import traces.")
        if "shared" in node_types:
            boundaries.append("Shared library boundary is inferred from reusable source folders and cross-folder imports.")
        if any(node.id == "deployment" for node in nodes):
            boundaries.append("Deployment boundary connects CI/hosting configuration to detected frontend and backend runtimes.")
        if any(edge.kind == "asset" for edge in edges):
            boundaries.append("Static asset boundary connects public/assets folders to pages or components that reference them.")
        if not boundaries:
            boundaries.append("Architecture boundaries are inferred from manifests, entry points, and folder roles; import evidence is sparse.")
        return boundaries[:6]

    @staticmethod
    def _dependency_flow(
        scan: RepositoryScan,
        nodes: list[ArchitectureNode],
        edges: list[ArchitectureEdge],
        metrics: dict[str, Any],
    ) -> list[str]:
        flow: list[str] = []
        if scan.package_managers:
            flow.append(f"Dependencies enter through {', '.join(scan.package_managers)} and configure {len([node for node in nodes if node.type in {'frontend', 'backend', 'shared'}])} runtime/source areas.")
        if metrics.get("imports_resolved"):
            flow.append(f"AST/import tracing resolved {metrics['imports_resolved']} imports into {len([edge for edge in edges if edge.kind == 'import'])} weighted folder relationships.")
        if scan.entry_points:
            flow.append(f"Runtime exploration should start at {', '.join(scan.entry_points[:4])}.")
        deployment_edges = [edge for edge in edges if edge.kind == "deployment"]
        if deployment_edges:
            flow.append("Deployment flow links CI/hosting manifests to the frontend/backend runtime nodes.")
        asset_edges = [edge for edge in edges if edge.kind == "asset"]
        if asset_edges:
            flow.append("Static assets are tied back to UI surfaces through direct references or framework public-folder conventions.")
        strongest = sorted(edges, key=lambda edge: edge.weight, reverse=True)[:3]
        if strongest:
            flow.append("Strongest graph edges: " + "; ".join(f"{edge.source} -> {edge.target} ({edge.label})" for edge in strongest))
        return flow[:6]

    @staticmethod
    def _summary(
        scan: RepositoryScan,
        nodes: list[ArchitectureNode],
        edges: list[ArchitectureEdge],
        metrics: dict[str, Any],
    ) -> str:
        frameworks = ", ".join(scan.frameworks[:5]) if scan.frameworks else "detected source conventions"
        connected = int(metrics.get("connected_ratio", 0) * 100)
        import_count = metrics.get("imports_resolved", 0)
        domains = ", ".join(sorted({node.group or node.type for node in nodes})[:6])
        return (
            f"The repository maps as a {frameworks} system with {len(nodes)} architecture nodes, "
            f"{len(edges)} weighted relationships, and {connected}% graph connectivity. "
            f"CodeSherpa resolved {import_count} import traces, then layered manifests, static assets, "
            f"and deployment configuration across {domains} domains."
        )
