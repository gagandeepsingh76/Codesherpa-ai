from __future__ import annotations

from typing import Any

from backend.models import (
    ArchitectureMap,
    ContributionPath,
    DependencyInsight,
    GoodFirstIssue,
    OwnershipArea,
    RepositoryIntelligence,
    RepositoryScan,
    RiskInsight,
    ComplexityScore,
)


class RepositoryIntelligenceAgent:
    name = "Repository Intelligence Agent"

    def run(self, scan: RepositoryScan, architecture: ArchitectureMap) -> RepositoryIntelligence:
        good_first_issues = self._good_first_issues(scan)
        contribution_paths = self._contribution_paths(scan)
        return RepositoryIntelligence(
            complexity=self._complexity(scan),
            risks=self._risks(scan),
            ownership=self._ownership(scan),
            dependency_insights=self._dependency_insights(scan.manifests),
            good_first_issues=good_first_issues,
            contribution_paths=contribution_paths,
            architecture_brief=self._architecture_brief(scan, architecture),
            demo_headline=self._demo_headline(scan),
            confidence="high" if scan.files else "low",
        )

    @staticmethod
    def _complexity(scan: RepositoryScan) -> ComplexityScore:
        file_count = len(scan.files)
        language_count = len(scan.languages)
        framework_count = len(scan.frameworks)
        folder_count = len(scan.folders)
        manifest_count = len(scan.manifests)
        score = min(
            100,
            int(
                min(file_count, 2500) / 35
                + language_count * 5
                + framework_count * 4
                + folder_count * 2
                + manifest_count * 3
                + len(scan.entry_points) * 2
            ),
        )
        if file_count:
            score = max(score, 8)
        if score < 25:
            level = "approachable"
        elif score < 50:
            level = "moderate"
        elif score < 75:
            level = "complex"
        else:
            level = "advanced"

        drivers = [
            f"{file_count} indexed files",
            f"{language_count} language families",
            f"{framework_count} framework signals",
            f"{folder_count} top-level areas",
        ]
        if scan.entry_points:
            drivers.append(f"{len(scan.entry_points)} entry points")
        if scan.package_managers:
            drivers.append(f"{', '.join(scan.package_managers)} package management")

        return ComplexityScore(
            score=score,
            level=level,
            summary=f"This repository looks {level}: enough structure to orient quickly, with complexity driven by {', '.join(drivers[:3]).lower()}.",
            drivers=drivers,
        )

    @staticmethod
    def _risks(scan: RepositoryScan) -> list[RiskInsight]:
        file_set = set(scan.files)
        risks: list[RiskInsight] = []
        if not any(path.lower().startswith("readme") for path in file_set):
            risks.append(
                RiskInsight(
                    title="Missing repository overview",
                    severity="high",
                    evidence=["README was not detected"],
                    recommendation="Add a README with purpose, setup, architecture, and contribution flow.",
                    confidence="high",
                )
            )
        if "CONTRIBUTING.md" not in file_set:
            risks.append(
                RiskInsight(
                    title="Contributor workflow is implicit",
                    severity="medium",
                    evidence=["CONTRIBUTING.md was not detected"],
                    recommendation="Add contribution expectations, local validation commands, and review guidance.",
                    confidence="high",
                )
            )
        if not any(path.startswith(("test/", "tests/", "__tests__/")) or "/test/" in path or "/tests/" in path for path in scan.files):
            risks.append(
                RiskInsight(
                    title="Testing surface is hard to discover",
                    severity="medium",
                    evidence=["No obvious test directory was detected"],
                    recommendation="Document test locations or add starter tests around core entry points.",
                    confidence="medium",
                )
            )
        if "package.json" in scan.manifests and not any(lock in file_set for lock in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")):
            risks.append(
                RiskInsight(
                    title="JavaScript dependencies may be less reproducible",
                    severity="medium",
                    evidence=["package.json exists without a detected JS lockfile"],
                    recommendation="Commit a package manager lockfile or document why dependency resolution is intentionally floating.",
                    confidence="medium",
                )
            )
        if scan.frameworks and len(scan.frameworks) >= 6:
            risks.append(
                RiskInsight(
                    title="High framework surface area",
                    severity="low",
                    evidence=scan.frameworks[:8],
                    recommendation="Document framework boundaries so contributors know which conventions apply where.",
                    confidence="medium",
                )
            )
        if not any(path.startswith(".github/workflows/") for path in scan.files):
            risks.append(
                RiskInsight(
                    title="CI workflow was not detected",
                    severity="low",
                    evidence=[".github/workflows was not detected"],
                    recommendation="Expose validation commands in docs or add CI workflows for contributor confidence.",
                    confidence="medium",
                )
            )
        return risks[:6]

    @staticmethod
    def _ownership(scan: RepositoryScan) -> list[OwnershipArea]:
        role_to_owner = {
            "frontend": ("Frontend surface", ["routes", "components", "user-facing flows"]),
            "backend": ("Backend/API surface", ["request handling", "services", "integration boundaries"]),
            "shared": ("Core platform", ["domain logic", "shared utilities", "package internals"]),
            "data": ("Data layer", ["schemas", "models", "persistence"]),
            "tests": ("Quality and regression", ["test coverage", "fixtures", "release confidence"]),
            "docs": ("Developer education", ["onboarding", "guides", "examples"]),
            "infra": ("Operations", ["CI", "deployment", "automation"]),
        }
        grouped: dict[str, list[str]] = {}
        for folder in scan.folders:
            grouped.setdefault(folder.role, []).append(folder.path)
        ownership: list[OwnershipArea] = []
        for role, paths in grouped.items():
            label, responsibilities = role_to_owner.get(role, ("Feature area", ["localized implementation", "repository-specific behavior"]))
            ownership.append(
                OwnershipArea(
                    area=label,
                    owner_hint=f"Likely owned by the team closest to {', '.join(paths[:2])}.",
                    paths=paths[:5],
                    responsibilities=responsibilities,
                    confidence="high" if role in role_to_owner else "low",
                )
            )
        return ownership[:7]

    @staticmethod
    def _dependency_insights(manifests: dict[str, Any]) -> list[DependencyInsight]:
        insights: list[DependencyInsight] = []
        package = manifests.get("package.json")
        if isinstance(package, dict):
            deps: dict[str, str] = {}
            for key in ("dependencies", "devDependencies"):
                deps.update(package.get(key, {}) or {})
            dependency_names = sorted(deps)[:10]
            floating = [name for name, version in deps.items() if isinstance(version, str) and version.startswith(("*", "latest"))]
            insights.append(
                DependencyInsight(
                    ecosystem="JavaScript",
                    signal=f"{len(deps)} dependencies declared in package.json",
                    dependencies=dependency_names,
                    risk="medium" if floating else "low",
                    recommendation="Review lockfile and framework-major versions before onboarding contributors."
                    if not floating
                    else f"Pin floating dependency versions: {', '.join(floating[:4])}.",
                )
            )

        requirements = manifests.get("requirements.txt")
        if isinstance(requirements, list):
            unpinned = [dep for dep in requirements if "==" not in dep and dep.strip()]
            insights.append(
                DependencyInsight(
                    ecosystem="Python",
                    signal=f"{len(requirements)} requirements detected",
                    dependencies=requirements[:10],
                    risk="medium" if unpinned else "low",
                    recommendation="Pin or constrain key runtime dependencies for reproducible onboarding."
                    if unpinned
                    else "Python dependencies appear pinned in requirements.txt.",
                )
            )

        if "pyproject.toml" in manifests:
            insights.append(
                DependencyInsight(
                    ecosystem="Python",
                    signal="pyproject.toml detected",
                    dependencies=[],
                    risk="low",
                    recommendation="Use pyproject metadata as the source of truth for tooling and package setup.",
                )
            )

        if "go.mod" in manifests:
            insights.append(
                DependencyInsight(
                    ecosystem="Go",
                    signal="go.mod detected",
                    dependencies=[],
                    risk="low",
                    recommendation="Start with module boundaries and package entry points before changing internals.",
                )
            )

        if "Cargo.toml" in manifests:
            insights.append(
                DependencyInsight(
                    ecosystem="Rust",
                    signal="Cargo.toml detected",
                    dependencies=[],
                    risk="low",
                    recommendation="Use crate boundaries and tests to identify contribution scope.",
                )
            )

        return insights[:5]

    @staticmethod
    def _good_first_issues(scan: RepositoryScan) -> list[GoodFirstIssue]:
        overview = [file.path for file in scan.important_files if file.role in {"overview", "manifest"}][:3]
        tests = [file.path for file in scan.important_files if file.role == "tests"][:3]
        entries = scan.entry_points[:3]
        docs = [folder.path for folder in scan.folders if folder.role == "docs"][:2]
        examples = [folder.path for folder in scan.folders if folder.path.lower() in {"examples", "example"}][:2]

        issues = [
            GoodFirstIssue(
                title="Add a contributor quickstart path",
                rationale="A short setup and first-file guide reduces onboarding friction for new contributors.",
                files=overview or docs or entries,
                labels=["good first issue", "documentation", "onboarding"],
                difficulty="easy",
                estimated_time="30-60 min",
                confidence="high" if overview or docs else "medium",
            ),
            GoodFirstIssue(
                title="Document the primary runtime entry point",
                rationale="The scanner found entry points that would benefit from a short architecture note.",
                files=entries or overview,
                labels=["good first issue", "architecture", "docs"],
                difficulty="easy",
                estimated_time="45-90 min",
                confidence="high" if entries else "low",
            ),
            GoodFirstIssue(
                title="Create a focused regression test around a visible behavior",
                rationale="A small test teaches project validation without requiring broad architecture changes.",
                files=tests or entries or overview,
                labels=["good first issue", "tests"],
                difficulty="medium",
                estimated_time="1-2 hr",
                confidence="medium" if tests else "low",
            ),
        ]
        if examples:
            issues.append(
                GoodFirstIssue(
                    title="Refresh an example to match current conventions",
                    rationale="Examples are excellent low-risk contribution surfaces because they are visible and scoped.",
                    files=examples,
                    labels=["good first issue", "examples"],
                    difficulty="easy",
                    estimated_time="45-90 min",
                    confidence="medium",
                )
            )
        return [issue for issue in issues if issue.files][:4]

    @staticmethod
    def _contribution_paths(scan: RepositoryScan) -> list[ContributionPath]:
        docs = [item.path for item in scan.important_files if item.role in {"overview", "contribution"}][:3]
        entries = scan.entry_points[:3]
        tests = [item.path for item in scan.important_files if item.role == "tests"][:3]
        source = [folder.path for folder in scan.folders if folder.role in {"frontend", "backend", "shared", "package"}][:4]
        return [
            ContributionPath(
                name="Documentation-first contributor",
                outcome="Land a helpful docs or onboarding improvement with low code risk.",
                steps=["Read overview and manifests", "Pick one confusing setup or architecture detail", "Add a compact explanation", "Validate links and commands"],
                files=docs or source[:2],
                difficulty="easy",
            ),
            ContributionPath(
                name="Behavior-first contributor",
                outcome="Understand one runtime path and add a small regression test.",
                steps=["Start at an entry point", "Trace one feature path", "Find adjacent tests", "Add or tighten one focused assertion"],
                files=entries + tests,
                difficulty="medium",
            ),
            ContributionPath(
                name="Feature-area contributor",
                outcome="Make a localized implementation change after mapping ownership boundaries.",
                steps=["Choose one ownership area", "Read its neighboring files", "Check dependency flow", "Keep the pull request scoped to one folder"],
                files=source,
                difficulty="medium",
            ),
        ]

    @staticmethod
    def _architecture_brief(scan: RepositoryScan, architecture: ArchitectureMap) -> str:
        frameworks = ", ".join(scan.frameworks[:4]) if scan.frameworks else "the detected source layout"
        owner_count = len({folder.role for folder in scan.folders})
        return f"{scan.name} is best explained as {frameworks} across {owner_count} ownership surfaces. {architecture.summary}"

    @staticmethod
    def _demo_headline(scan: RepositoryScan) -> str:
        if scan.frameworks:
            return f"Mapped {scan.name} into {len(scan.frameworks)} framework signals and {len(scan.folders)} contributor surfaces."
        return f"Mapped {scan.name} into {len(scan.folders)} contributor surfaces with evidence-backed onboarding guidance."
