from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.models import AnalysisResult, ChatResponse
from backend.utils.paths import BACKEND_MEMORY_FILE, ensure_workspace


class MemoryStore:
    def __init__(self, path: Path = BACKEND_MEMORY_FILE) -> None:
        ensure_workspace()
        self.path = path

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"repositories": {}, "questions": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"repositories": {}, "questions": []}

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def save_analysis(self, result: AnalysisResult) -> None:
        data = self._load()
        repositories = data.setdefault("repositories", {})
        repositories[result.repo_id] = result.model_dump(mode="json")
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save(data)

    def get_analysis(self, repo_id: str) -> dict[str, Any] | None:
        data = self._load()
        return data.get("repositories", {}).get(repo_id)

    def get_analysis_by_url(self, repo_url: str) -> dict[str, Any] | None:
        data = self._load()
        normalized = repo_url.strip().removesuffix(".git").lower()
        for analysis in data.get("repositories", {}).values():
            stored_url = str(analysis.get("repo_url", "")).strip().removesuffix(".git").lower()
            if stored_url == normalized:
                return analysis
        return None

    def list_repositories(self) -> list[dict[str, Any]]:
        data = self._load()
        return list(data.get("repositories", {}).values())

    def remember_question(self, repo_id: str, question: str, response: ChatResponse) -> None:
        data = self._load()
        data.setdefault("questions", []).append(
            {
                "repo_id": repo_id,
                "question": question,
                "answer_preview": response.answer[:500],
                "cited_files": response.cited_files,
                "confidence": response.confidence,
                "asked_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        data["questions"] = data["questions"][-200:]
        self._save(data)
