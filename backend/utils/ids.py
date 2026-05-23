from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse


def stable_repo_id(repo_url: str) -> str:
    normalized = repo_url.strip().removesuffix(".git").lower()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def safe_repo_name(repo_url: str) -> str:
    parsed = urlparse(repo_url)
    tail = parsed.path.strip("/").removesuffix(".git")
    owner_repo = tail.replace("/", "__") or parsed.netloc
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", owner_repo)


def event_id(repo_id: str, title: str, index: int) -> str:
    seed = f"{repo_id}:{index}:{title}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
