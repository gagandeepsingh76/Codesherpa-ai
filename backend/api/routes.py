from __future__ import annotations

import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.models import AnalysisResult, ChatRequest, ChatResponse, RepoAnalyzeRequest, TimelineEvent
from backend.workflows.orchestrator import RepositoryUnderstandingWorkflow, sse


router = APIRouter()
workflow = RepositoryUnderstandingWorkflow()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "codesherpa-ai"}


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(payload: RepoAnalyzeRequest) -> AnalysisResult:
    try:
        return await workflow.run(str(payload.repo_url), use_cache=payload.use_cache)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    return await workflow.chat(payload.repo_id, payload.message)


@router.get("/timeline/stream")
async def timeline_stream(repo_url: str = Query(..., min_length=10), use_cache: bool = Query(False)) -> StreamingResponse:
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def emit(event: TimelineEvent) -> None:
        await queue.put(sse("timeline", event.model_dump(mode="json")))

    async def run_analysis() -> None:
        try:
            result = await workflow.run(repo_url, emit, use_cache=use_cache)
            await queue.put(sse("complete", result.model_dump(mode="json")))
        except Exception as exc:
            await queue.put(sse("error", {"message": str(exc)}))
        finally:
            await queue.put(None)

    async def generator() -> AsyncIterator[str]:
        task = asyncio.create_task(run_analysis())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            await task

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.get("/timeline/{repo_id}", response_model=list[TimelineEvent])
async def timeline(repo_id: str) -> list[TimelineEvent]:
    return workflow.timeline(repo_id)


@router.get("/architecture/{repo_id}")
async def architecture(repo_id: str) -> dict:
    data = workflow.architecture(repo_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Repository analysis not found.")
    return data


@router.get("/onboarding/{repo_id}")
async def onboarding(repo_id: str) -> dict:
    data = workflow.onboarding(repo_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Repository analysis not found.")
    return data


@router.get("/intelligence/{repo_id}")
async def intelligence(repo_id: str) -> dict:
    data = workflow.intelligence(repo_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Repository intelligence not found.")
    return data


@router.get("/code-intelligence/{repo_id}")
async def code_intelligence(repo_id: str) -> dict:
    data = workflow.code_intelligence_payload(repo_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Repository code intelligence not found.")
    return data


@router.get("/repo-summary/{repo_id}")
async def repo_summary(repo_id: str) -> dict:
    data = workflow.repo_summary(repo_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Repository analysis not found.")
    return data
