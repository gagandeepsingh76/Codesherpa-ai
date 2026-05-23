from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from git import GitCommandError, Repo

from backend.utils.ids import safe_repo_name
from backend.utils.paths import REPO_ROOT, ensure_workspace


class GitService:
    def __init__(self) -> None:
        ensure_workspace()

    async def clone_or_update(self, repo_url: str) -> Path:
        return await asyncio.to_thread(self._clone_or_update_sync, repo_url)

    def _clone_or_update_sync(self, repo_url: str) -> Path:
        target = REPO_ROOT / safe_repo_name(repo_url)
        if target.exists() and (target / ".git").exists():
            repo = Repo(target)
            try:
                repo.remotes.origin.fetch(depth=1, prune=True)
                repo.git.reset("--hard", "origin/HEAD")
            except GitCommandError:
                shutil.rmtree(target)
                Repo.clone_from(repo_url, target, multi_options=["--depth=1"])
        else:
            if target.exists():
                shutil.rmtree(target)
            Repo.clone_from(repo_url, target, multi_options=["--depth=1"])
        return target

    async def default_branch(self, repo_path: Path) -> str | None:
        return await asyncio.to_thread(self._default_branch_sync, repo_path)

    @staticmethod
    def _default_branch_sync(repo_path: Path) -> str | None:
        try:
            repo = Repo(repo_path)
            branch = repo.active_branch.name
            return branch
        except Exception:
            return None
