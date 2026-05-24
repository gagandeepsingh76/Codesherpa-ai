from __future__ import annotations

import json
import os
import re
import tomllib
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

from backend.models import FolderInsight, ImportantFile, RepositoryScan
from backend.utils.ids import stable_repo_id


EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "coverage",
    ".turbo",
    ".cache",
    ".codesherpa",
}

LANGUAGE_BY_EXTENSION = {
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".py": "Python",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".md": "Markdown",
    ".css": "CSS",
    ".scss": "CSS",
    ".html": "HTML",
    ".sql": "SQL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
}

MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "composer.json",
    "Gemfile",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "vite.config.ts",
    "vite.config.js",
    "vite.config.mjs",
    "tailwind.config.ts",
    "tailwind.config.js",
    "tailwind.config.mjs",
    "tsconfig.json",
    "tsconfig.base.json",
    "vercel.json",
    "render.yaml",
    "render.yml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "nest-cli.json",
    "schema.prisma",
}

IMPORTANT_NAMES = {
    "README.md": ("overview", "Primary repository overview and setup context."),
    "CONTRIBUTING.md": ("contribution", "Contributor process and project norms."),
    "package.json": ("manifest", "JavaScript package manifest and scripts."),
    "pyproject.toml": ("manifest", "Python project manifest and tooling."),
    "requirements.txt": ("manifest", "Python dependency list."),
    "go.mod": ("manifest", "Go module and dependency definition."),
    "Cargo.toml": ("manifest", "Rust package manifest."),
    "Dockerfile": ("infra", "Container runtime definition."),
    "docker-compose.yml": ("infra", "Local service composition."),
    "README": ("overview", "Repository overview."),
}


class RepositoryScanner:
    def __init__(self, max_files: int = 10_000, max_file_bytes: int = 120_000) -> None:
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes

    def scan(self, repo_url: str, repo_path: Path, default_branch: str | None) -> RepositoryScan:
        files = self._walk_files(repo_path)
        languages = self._language_counts(files)
        manifests = self._read_manifests(repo_path, files)
        frameworks = self._detect_frameworks(manifests, files)
        package_managers = self._detect_package_managers(files)
        entry_points = self._detect_entry_points(files)
        important_files = self._rank_important_files(files, frameworks)
        folders = self._folder_insights(files, frameworks)
        readme_excerpt = self._read_readme(repo_path)

        return RepositoryScan(
            repo_id=stable_repo_id(repo_url),
            repo_url=repo_url,
            name=repo_path.name.replace("__", "/"),
            path=str(repo_path),
            default_branch=default_branch,
            files=files,
            languages=dict(languages),
            manifests=manifests,
            frameworks=frameworks,
            package_managers=package_managers,
            entry_points=entry_points,
            important_files=important_files,
            folders=folders,
            readme_excerpt=readme_excerpt,
            confidence="high" if files else "low",
        )

    def _walk_files(self, repo_path: Path) -> list[str]:
        collected: list[str] = []
        for root, dirnames, filenames in os.walk(repo_path):
            dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS]
            for filename in filenames:
                if len(collected) >= self.max_files:
                    return sorted(collected)
                path = Path(root) / filename
                relative = path.relative_to(repo_path)
                if set(relative.parts) & EXCLUDED_DIRS:
                    continue
                try:
                    if path.stat().st_size > self.max_file_bytes:
                        continue
                except OSError:
                    continue
                collected.append(relative.as_posix())
        return sorted(collected)

    @staticmethod
    def _language_counts(files: list[str]) -> Counter[str]:
        counter: Counter[str] = Counter()
        for file in files:
            language = LANGUAGE_BY_EXTENSION.get(Path(file).suffix.lower())
            if language:
                counter[language] += 1
        return counter

    def _read_manifests(self, repo_path: Path, files: list[str]) -> dict[str, Any]:
        manifests: dict[str, Any] = {}
        manifest_files = [
            file
            for file in files
            if Path(file).name in MANIFEST_NAMES or file in MANIFEST_NAMES
        ][:120]
        for file in sorted(manifest_files):
            path = repo_path / file
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            manifests[file] = self._parse_manifest(file, text)
        return manifests

    @staticmethod
    def _parse_manifest(file: str, text: str) -> Any:
        name = Path(file).name
        try:
            if name.endswith(".json"):
                return json.loads(RepositoryScanner._strip_json_comments(text))
            if name.endswith(".toml"):
                return tomllib.loads(text)
            if name.startswith("requirements") and name.endswith(".txt"):
                return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
            if name in {"render.yaml", "render.yml", "docker-compose.yml", "docker-compose.yaml"}:
                return yaml.safe_load(text) or {}
            if name == "go.mod":
                return {"module": next((line.replace("module", "").strip() for line in text.splitlines() if line.startswith("module ")), None)}
        except Exception:
            return {"raw_preview": text[:2000], "parse_error": True}
        return {"raw_preview": text[:4000]}

    @staticmethod
    def _strip_json_comments(text: str) -> str:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        return re.sub(r"(^|\s)//.*$", "", text, flags=re.MULTILINE)

    @staticmethod
    def _detect_frameworks(manifests: dict[str, Any], files: list[str]) -> list[str]:
        detected: set[str] = set()
        deps: dict[str, Any] = {}
        for file, manifest in manifests.items():
            if Path(file).name == "package.json" and isinstance(manifest, dict):
                for key in ("dependencies", "devDependencies", "peerDependencies"):
                    deps.update(manifest.get(key, {}) or {})

        dependency_map = {
            "next": "Next.js",
            "react": "React",
            "vue": "Vue",
            "nuxt": "Nuxt",
            "svelte": "Svelte",
            "@sveltejs/kit": "SvelteKit",
            "express": "Express",
            "fastify": "Fastify",
            "nestjs": "NestJS",
            "@nestjs/core": "NestJS",
            "@nestjs/common": "NestJS",
            "vite": "Vite",
            "tailwindcss": "Tailwind CSS",
            "framer-motion": "Framer Motion",
            "prisma": "Prisma",
            "@prisma/client": "Prisma",
            "drizzle-orm": "Drizzle ORM",
            "vitest": "Vitest",
            "jest": "Jest",
            "playwright": "Playwright",
        }
        for package_name, framework in dependency_map.items():
            if package_name in deps:
                detected.add(framework)

        requirement_lines: list[str] = []
        pyproject_payloads: list[dict[str, Any]] = []
        for file, manifest in manifests.items():
            name = Path(file).name
            if name.startswith("requirements") and isinstance(manifest, list):
                requirement_lines.extend(str(item) for item in manifest)
            if name == "pyproject.toml" and isinstance(manifest, dict):
                pyproject_payloads.append(manifest)
        requirements = "\n".join(requirement_lines)
        py_text = "\n".join(json.dumps(payload).lower() for payload in pyproject_payloads)
        python_signal = f"{requirements}\n{py_text}".lower()
        python_map = {
            "fastapi": "FastAPI",
            "django": "Django",
            "flask": "Flask",
            "sqlalchemy": "SQLAlchemy",
            "pydantic": "Pydantic",
            "pytest": "Pytest",
            "langchain": "LangChain",
            "langgraph": "LangGraph",
            "crewai": "CrewAI",
            "chromadb": "ChromaDB",
        }
        for needle, framework in python_map.items():
            if needle in python_signal:
                detected.add(framework)

        file_set = set(files)
        file_names = {Path(file).name for file in files}
        if any(name.startswith("next.config.") for name in file_names):
            detected.add("Next.js")
        if any("/app/" in f"/{file}" or file.startswith("app/") for file in file_set) and "Next.js" in detected:
            detected.add("Next.js App Router")
        if any(name.startswith("vite.config.") for name in file_names):
            detected.add("Vite")
        if any(name.startswith("tailwind.config.") for name in file_names):
            detected.add("Tailwind CSS")
        if "schema.prisma" in file_names:
            detected.add("Prisma")
        if "manage.py" in file_names and any("settings.py" in file for file in file_set):
            detected.add("Django")
        manifest_names = {Path(file).name for file in manifests}
        if "go.mod" in manifest_names:
            detected.add("Go")
        if "Cargo.toml" in manifest_names:
            detected.add("Rust")

        return sorted(detected)

    @staticmethod
    def _detect_package_managers(files: list[str]) -> list[str]:
        signals = {
            "package-lock.json": "npm",
            "pnpm-lock.yaml": "pnpm",
            "yarn.lock": "Yarn",
            "uv.lock": "uv",
            "poetry.lock": "Poetry",
            "requirements.txt": "pip",
            "Cargo.lock": "Cargo",
            "go.sum": "Go modules",
        }
        file_names = {Path(file).name for file in files}
        return [manager for file, manager in signals.items() if file in file_names]

    @staticmethod
    def _detect_entry_points(files: list[str]) -> list[str]:
        file_set = set(files)
        candidates = [
            "app/page.tsx",
            "app/layout.tsx",
            "src/app/page.tsx",
            "src/app/layout.tsx",
            "pages/index.tsx",
            "src/main.tsx",
            "src/main.ts",
            "src/index.tsx",
            "main.py",
            "app.py",
            "backend/main.py",
            "server.js",
            "src/server.ts",
            "cmd/main.go",
        ]
        entry_points = [file for file in candidates if file in file_set]
        entry_points.extend(sorted(file for file in files if re.search(r"(^|/)api/(route|index)\.(ts|tsx|js|py)$", file))[:12])
        nested_patterns = [
            r"(^|/)app/(layout|page)\.(tsx|jsx|ts|js)$",
            r"(^|/)pages/index\.(tsx|jsx|ts|js)$",
            r"(^|/)src/main\.(tsx|jsx|ts|js)$",
            r"(^|/)(main|app)\.py$",
            r"(^|/)manage\.py$",
            r"(^|/)(server|index)\.(ts|js)$",
        ]
        for pattern in nested_patterns:
            entry_points.extend(sorted(file for file in files if re.search(pattern, file))[:8])
        entry_points = list(dict.fromkeys(entry_points))
        return entry_points[:20]

    @staticmethod
    def _rank_important_files(files: list[str], frameworks: list[str]) -> list[ImportantFile]:
        important: list[ImportantFile] = []
        file_set = set(files)
        for file, (role, reason) in IMPORTANT_NAMES.items():
            if file in file_set:
                important.append(ImportantFile(path=file, role=role, reason=reason, confidence="high"))

        patterns = [
            (r"(^|/)app/(layout|page)\.tsx$", "entry", "Next.js App Router entry point."),
            (r"(^|/)pages/index\.(tsx|jsx|ts|js)$", "entry", "Pages router application entry."),
            (r"(^|/)api/.+route\.(ts|js)$", "api", "API route implementation."),
            (r"(^|/)(auth|middleware)\.(ts|js|py)$", "auth", "Authentication or request middleware signal."),
            (r"(^|/)schema\.(prisma|sql)$", "data", "Database schema definition."),
            (r"(^|/)models?/.+\.(py|ts|js)$", "data", "Domain model area."),
            (r"(^|/)tests?/.+", "tests", "Test coverage area."),
            (r"(^|/)\.github/workflows/.+\.ya?ml$", "ci", "CI workflow configuration."),
        ]
        seen = {item.path for item in important}
        for pattern, role, reason in patterns:
            for file in files:
                if file in seen:
                    continue
                if re.search(pattern, file):
                    important.append(ImportantFile(path=file, role=role, reason=reason, confidence="medium"))
                    seen.add(file)
                    break

        if "FastAPI" in frameworks:
            for file in files:
                if file.endswith(".py") and ("main" in Path(file).stem or "api" in file.lower()) and file not in seen:
                    important.append(ImportantFile(path=file, role="api", reason="Likely FastAPI application or API module.", confidence="medium"))
                    seen.add(file)
                    break

        return important[:18]

    @staticmethod
    def _folder_insights(files: list[str], frameworks: list[str]) -> list[FolderInsight]:
        counts: defaultdict[str, int] = defaultdict(int)
        for file in files:
            root = file.split("/", 1)[0]
            if root and root != file:
                counts[root] += 1

        insights: list[FolderInsight] = []
        for folder, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:16]:
            role, description, confidence = RepositoryScanner._classify_folder(folder, frameworks)
            insights.append(
                FolderInsight(
                    path=folder,
                    role=role,
                    description=description,
                    file_count=count,
                    confidence=confidence,
                )
            )
        return insights

    @staticmethod
    def _classify_folder(folder: str, frameworks: list[str]) -> tuple[str, str, str]:
        normalized = folder.lower()
        if normalized in {"app", "pages"}:
            if "Next.js" in frameworks:
                return "frontend", "Application routing and UI surface.", "high"
            return "application", "Application entry and routing surface.", "medium"
        if normalized in {"src", "lib", "packages"}:
            return "shared", "Core implementation area with reusable source files.", "medium"
        if normalized in {"api", "server", "backend"}:
            return "backend", "Backend or API implementation boundary.", "medium"
        if normalized in {"components", "ui"}:
            return "frontend", "Reusable UI component layer.", "medium"
        if normalized in {"docs", "documentation"}:
            return "docs", "Documentation and learning material.", "high"
        if normalized in {"test", "tests", "__tests__"}:
            return "tests", "Automated tests and validation.", "high"
        if normalized in {".github", "infra", "deploy", "scripts"}:
            return "infra", "Automation, deployment, or operational scripts.", "medium"
        return "package", "Repository package or feature area.", "low"

    @staticmethod
    def _read_readme(repo_path: Path) -> str | None:
        for name in ("README.md", "README"):
            path = repo_path / name
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="ignore")
                compact = re.sub(r"\s+", " ", text).strip()
                return compact[:1200]
        return None
