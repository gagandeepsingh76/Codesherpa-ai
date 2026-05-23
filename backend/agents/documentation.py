from __future__ import annotations

from backend.models import ArchitectureMap, RepositoryScan


class DocumentationAgent:
    name = "Documentation Agent"

    def recommendations(self, scan: RepositoryScan, architecture: ArchitectureMap) -> list[str]:
        docs = []
        has_readme = any(item.role == "overview" for item in scan.important_files)
        has_contributing = any(item.role == "contribution" for item in scan.important_files)
        if not has_readme:
            docs.append("Create a README with purpose, setup, scripts, and architecture overview.")
        if not has_contributing:
            docs.append("Add a CONTRIBUTING guide with branch, test, and review expectations.")
        if architecture.boundaries:
            docs.append("Add an architecture note that explains the detected boundaries and entry points.")
        if scan.frameworks:
            docs.append(f"Document local conventions for {', '.join(scan.frameworks[:3])}.")
        return docs[:5]

    def summary(self, scan: RepositoryScan, architecture: ArchitectureMap) -> str:
        frameworks = ", ".join(scan.frameworks[:4]) if scan.frameworks else "detected source structure"
        entry = ", ".join(scan.entry_points[:3]) if scan.entry_points else "the top-level source folders"
        return f"{scan.name} is best approached as a {frameworks} codebase. Start at {entry}, then use the architecture map to follow source folders, tests, and configuration."
