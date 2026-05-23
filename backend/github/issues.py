from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IssueSignal:
    category: str
    matches: list[str]


class IssueSignalExtractor:
    """Small deterministic issue parser used by the Issue Debugging Agent."""

    SIGNALS = {
        "auth": ["auth", "login", "logout", "session", "token", "oauth", "permission"],
        "api": ["api", "route", "endpoint", "request", "response", "http"],
        "data": ["database", "db", "schema", "migration", "model", "query"],
        "ui": ["component", "page", "layout", "button", "form", "render"],
        "build": ["build", "compile", "bundle", "install", "dependency", "package"],
        "test": ["test", "spec", "coverage", "ci", "workflow"],
    }

    def extract(self, title: str, body: str = "") -> list[IssueSignal]:
        text = f"{title}\n{body}".lower()
        tokens = set(re.findall(r"[a-z][a-z0-9_-]{2,}", text))
        signals: list[IssueSignal] = []
        for category, keywords in self.SIGNALS.items():
            matches = [keyword for keyword in keywords if keyword in tokens or keyword in text]
            if matches:
                signals.append(IssueSignal(category=category, matches=matches))
        return signals
