from __future__ import annotations

from backend.models import ContributorPlan, ContributorTask, ImportantFile, OnboardingStep, RepositoryScan


class OnboardingAgent:
    name = "Onboarding Agent"

    def run(self, scan: RepositoryScan) -> ContributorPlan:
        overview_files = [item.path for item in scan.important_files if item.role in {"overview", "manifest"}][:4]
        entry_files = scan.entry_points[:4]
        test_files = [item.path for item in scan.important_files if item.role == "tests"][:3]
        beginner_files = self._beginner_files(scan)

        roadmap = [
            OnboardingStep(
                title="Understand the repository contract",
                description="Read the overview and manifests to learn the stack, scripts, and project intent.",
                files=overview_files or [item.path for item in beginner_files[:2]],
                difficulty="easy",
                estimate="15-25 min",
            ),
            OnboardingStep(
                title="Trace the runtime entry points",
                description="Open the main application files and follow how requests, pages, or commands enter the system.",
                files=entry_files or [item.path for item in beginner_files[:2]],
                difficulty="medium",
                estimate="25-40 min",
            ),
            OnboardingStep(
                title="Map one feature end to end",
                description="Pick a small feature folder and trace UI, service, data, and tests where present.",
                files=[folder.path for folder in scan.folders[:3]],
                difficulty="medium",
                estimate="45-60 min",
            ),
            OnboardingStep(
                title="Make a low-risk contribution",
                description="Start with docs, tests, examples, or localized fixes before changing cross-cutting architecture.",
                files=test_files or overview_files or [item.path for item in beginner_files[:2]],
                difficulty="easy",
                estimate="30-90 min",
            ),
        ]

        tasks = self._tasks(scan, beginner_files)
        learning_sequence = [
            "Repository purpose",
            "Dependency manifests",
            "Runtime entry points",
            "Core folders",
            "Tests and contribution flow",
            "First scoped pull request",
        ]
        return ContributorPlan(
            roadmap=roadmap,
            beginner_files=beginner_files,
            recommended_tasks=tasks,
            learning_sequence=learning_sequence,
            confidence="high" if beginner_files else "medium",
        )

    @staticmethod
    def _beginner_files(scan: RepositoryScan) -> list[ImportantFile]:
        priority = {"overview": 0, "manifest": 1, "entry": 2, "tests": 3, "ci": 4}
        return sorted(scan.important_files, key=lambda item: priority.get(item.role, 8))[:8]

    @staticmethod
    def _tasks(scan: RepositoryScan, beginner_files: list[ImportantFile]) -> list[ContributorTask]:
        files = [item.path for item in beginner_files[:3]]
        tasks = [
            ContributorTask(
                title="Improve contributor setup notes",
                why="Setup documentation is usually a safe first contribution and helps future onboarding.",
                files=files,
                difficulty="easy",
            ),
            ContributorTask(
                title="Add or refine a focused test",
                why="Tests teach behavior without requiring broad architecture changes.",
                files=[item.path for item in scan.important_files if item.role == "tests"][:3] or files,
                difficulty="medium",
            ),
            ContributorTask(
                title="Document one architecture path",
                why="A short explanation of an entry point creates durable value for contributors.",
                files=scan.entry_points[:3] or files,
                difficulty="medium",
            ),
        ]
        if not scan.entry_points:
            tasks.append(
                ContributorTask(
                    title="Identify and document the primary entry point",
                    why="The scanner did not find a canonical entry point, so clarifying this would materially improve onboarding.",
                    files=files,
                    difficulty="easy",
                )
            )
        return tasks[:4]
