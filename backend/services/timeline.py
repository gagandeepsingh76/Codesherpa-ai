from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from backend.models import Confidence, TimelineEvent
from backend.utils.ids import event_id

TimelineEmitter = Callable[[TimelineEvent], Awaitable[None] | None]


class TimelineRecorder:
    def __init__(self, repo_id: str, emitter: TimelineEmitter | None = None) -> None:
        self.repo_id = repo_id
        self.emitter = emitter
        self.events: list[TimelineEvent] = []

    async def add(
        self,
        agent: str,
        title: str,
        detail: str,
        status: str = "completed",
        confidence: Confidence = "medium",
        metadata: dict[str, Any] | None = None,
    ) -> TimelineEvent:
        event = TimelineEvent(
            id=event_id(self.repo_id, title, len(self.events) + 1),
            timestamp=datetime.now(timezone.utc),
            agent=agent,
            title=title,
            detail=detail,
            status=status,  # type: ignore[arg-type]
            confidence=confidence,
            metadata=metadata or {},
        )
        self.events.append(event)
        if self.emitter:
            maybe = self.emitter(event)
            if maybe is not None:
                await maybe
        return event
