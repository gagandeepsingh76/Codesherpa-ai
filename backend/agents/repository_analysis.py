from __future__ import annotations

from backend.models import RepositoryScan, RepositorySummary


class RepositoryAnalysisAgent:
    name = "Repository Analysis Agent"

    def run(self, scan: RepositoryScan) -> RepositorySummary:
        recommendations = self._recommendations(scan)
        description = self._description(scan)
        return RepositorySummary(
            repo_id=scan.repo_id,
            repo_url=scan.repo_url,
            name=scan.name,
            default_branch=scan.default_branch,
            description=description,
            languages=scan.languages,
            frameworks=scan.frameworks,
            entry_points=scan.entry_points,
            package_managers=scan.package_managers,
            important_files=scan.important_files,
            folders=scan.folders,
            recommendations=recommendations,
            confidence=scan.confidence,
        )

    @staticmethod
    def _description(scan: RepositoryScan) -> str:
        if scan.readme_excerpt:
            first_sentence = scan.readme_excerpt.split(". ", 1)[0].strip()
            if 30 <= len(first_sentence) <= 220:
                return first_sentence
        framework_text = ", ".join(scan.frameworks[:4]) if scan.frameworks else "detected source files"
        language_text = ", ".join(list(scan.languages.keys())[:3]) if scan.languages else "multiple languages"
        return f"{scan.name} appears to be a {language_text} repository built around {framework_text}."

    @staticmethod
    def _recommendations(scan: RepositoryScan) -> list[str]:
        recommendations: list[str] = []
        if not any(file.path.lower().startswith("readme") for file in scan.important_files):
            recommendations.append("Add or expand a README so contributors can understand setup and intent quickly.")
        if not any(file.role == "tests" for file in scan.important_files):
            recommendations.append("Expose the main test entry points in documentation or add starter tests for contributors.")
        if scan.entry_points:
            recommendations.append(f"Start architecture review at `{scan.entry_points[0]}` and follow imports outward.")
        if scan.frameworks:
            recommendations.append(f"Document framework conventions for {', '.join(scan.frameworks[:3])}.")
        if not recommendations:
            recommendations.append("Repository has strong onboarding signals; keep architecture notes close to the entry points.")
        return recommendations[:4]
