from __future__ import annotations

from backend.models import ContributorTask, RepositoryScan


class IssueDebuggingAgent:
    name = "Issue Debugging Agent"

    KEYWORDS = {
        "auth": ["auth", "login", "session", "token", "oauth", "password"],
        "api": ["api", "route", "endpoint", "request", "response"],
        "data": ["database", "db", "schema", "migration", "model", "sql"],
        "ui": ["page", "component", "button", "form", "layout", "render"],
        "build": ["build", "compile", "bundle", "dependency", "install"],
        "test": ["test", "spec", "coverage", "failing"],
    }

    def run(self, issue_text: str, scan: RepositoryScan) -> list[ContributorTask]:
        text = issue_text.lower()
        matched_roles = {
            role for role, keywords in self.KEYWORDS.items() if any(keyword in text for keyword in keywords)
        }
        tasks: list[ContributorTask] = []
        for role in matched_roles:
            files = [item.path for item in scan.important_files if item.role == role][:4]
            if not files and role == "ui":
                files = [folder.path for folder in scan.folders if folder.role == "frontend"][:3]
            if not files and role == "build":
                files = [item.path for item in scan.important_files if item.role == "manifest"][:4]
            tasks.append(
                ContributorTask(
                    title=f"Inspect likely {role} surface",
                    why=f"Issue language matched {role}-related repository signals.",
                    files=files or scan.entry_points[:3],
                    difficulty="medium",
                )
            )
        return tasks or [
            ContributorTask(
                title="Start from entry points and recent important files",
                why="The issue text did not strongly match a subsystem, so begin with the observed runtime entry points.",
                files=scan.entry_points[:3] or [item.path for item in scan.important_files[:3]],
                difficulty="medium",
            )
        ]
