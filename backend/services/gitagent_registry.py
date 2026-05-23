from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

from backend.utils.paths import AGENT_MANIFEST, AGENT_RULES, AGENT_SOUL, PROJECT_ROOT


class GitAgentRegistry:
    """Loads the repo-native GitAgent contract used by the backend workflow."""

    @cached_property
    def manifest(self) -> dict[str, Any]:
        return self._read_yaml(AGENT_MANIFEST)

    @cached_property
    def soul(self) -> str:
        return AGENT_SOUL.read_text(encoding="utf-8")

    @cached_property
    def rules(self) -> str:
        return AGENT_RULES.read_text(encoding="utf-8")

    @cached_property
    def agents(self) -> dict[str, dict[str, Any]]:
        configured = self.manifest.get("agents", {})
        loaded: dict[str, dict[str, Any]] = {}
        for key, relative_path in configured.items():
            path = PROJECT_ROOT / str(relative_path)
            if path.exists():
                loaded[key] = self._read_yaml(path)
        return loaded

    @cached_property
    def skills(self) -> dict[str, str]:
        skills: dict[str, str] = {}
        for name in self.manifest.get("skills", []):
            skill_file = PROJECT_ROOT / "skills" / name / "SKILL.md"
            if skill_file.exists():
                skills[name] = skill_file.read_text(encoding="utf-8")
        return skills

    def system_context(self) -> str:
        return "\n\n".join(
            [
                "# SOUL",
                self.soul,
                "# RULES",
                self.rules,
            ]
        )

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
