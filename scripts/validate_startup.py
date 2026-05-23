from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.request import urlopen

import yaml


ROOT = Path(__file__).resolve().parents[1]


def require(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Missing required path: {path.relative_to(ROOT)}")


def main() -> None:
    manifest_path = ROOT / "agent.yaml"
    require(manifest_path)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    for relative_path in ["SOUL.md", "RULES.md", "memory/repositories.json"]:
        require(ROOT / relative_path)

    for skill in manifest.get("skills", []):
        require(ROOT / "skills" / skill / "SKILL.md")

    for relative_path in (manifest.get("agents") or {}).values():
        require(ROOT / str(relative_path))

    memory_schema = json.loads((ROOT / "memory" / "repositories.json").read_text(encoding="utf-8"))
    if "schema" not in memory_schema:
        raise SystemExit("memory/repositories.json must include schema metadata")

    backend_url = os.getenv("CODESHERPA_BACKEND_URL") or os.getenv("NEXT_PUBLIC_API_URL")
    if not backend_url:
        backend_url = f"http://127.0.0.1:{os.getenv('BACKEND_PORT', '8000')}"
    health_url = f"{backend_url.rstrip('/')}/health"

    try:
        with urlopen(health_url, timeout=2) as response:
            if response.status != 200:
                raise SystemExit("Backend health check did not return 200")
            print(response.read().decode("utf-8"))
    except Exception:
        print(f"Backend health check skipped: service is not running on {health_url}")

    print("CodeSherpa startup validation passed")


if __name__ == "__main__":
    main()
