from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
WORKSPACE_ROOT = BACKEND_ROOT / ".codesherpa"
REPO_ROOT = WORKSPACE_ROOT / "repos"
BACKEND_MEMORY_FILE = BACKEND_ROOT / "memory" / "codesherpa_memory.json"
AGENT_MANIFEST = PROJECT_ROOT / "agent.yaml"
AGENT_SOUL = PROJECT_ROOT / "SOUL.md"
AGENT_RULES = PROJECT_ROOT / "RULES.md"


def ensure_workspace() -> None:
    REPO_ROOT.mkdir(parents=True, exist_ok=True)
    BACKEND_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
