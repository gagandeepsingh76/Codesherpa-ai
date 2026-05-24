from __future__ import annotations

import os
from typing import Any

from openai import AsyncOpenAI

from backend.services.gitagent_registry import GitAgentRegistry


class LLMService:
    def __init__(self, registry: GitAgentRegistry) -> None:
        self.registry = registry
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None
        self.model = os.getenv("CODESHERPA_MODEL", "gpt-4.1-mini")

    async def answer_with_context(self, question: str, context: dict[str, Any]) -> str | None:
        if not self.client:
            return None

        prompt = (
            f"{self.registry.system_context()}\n\n"
            "# Grounded Repository Context\n"
            f"{context}\n\n"
            "# User Question\n"
            f"{question}\n\n"
            "Answer with concise repository-specific guidance. Use only the provided retrieved files, symbols, routes, "
            "middleware, providers, runtime boundaries, and dependency evidence. Cite exact file paths and symbol or "
            "route names that appear in the context. If the evidence is missing, say what could not be proven."
        )
        response = await self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.2,
            max_output_tokens=900,
        )
        return response.output_text
