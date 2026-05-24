from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routes import router


load_dotenv(PROJECT_ROOT / ".env")


def allowed_origins() -> list[str]:
    configured = os.getenv("CODESHERPA_ALLOWED_ORIGINS", "")
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:3010",
        "http://127.0.0.1:3010",
        "http://localhost:3020",
        "http://127.0.0.1:3020",
    ]
    origins = defaults + [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    return list(dict.fromkeys(origins))


app = FastAPI(
    title="CodeSherpa AI API",
    description="GitAgent-powered repository understanding backend.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_origin_regex=os.getenv("CODESHERPA_ALLOW_ORIGIN_REGEX", r"https?://(localhost|127\.0\.0\.1):[0-9]+"),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
