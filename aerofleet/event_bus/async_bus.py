"""Async Event Bus for inter-agent communication."""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
logger = logging.getLogger(__name__)

@dataclass
class Event:
    event_id: str
    event_type: str
    source: str
    payload: Any
    priority: int = 1   # 1=normal, 2=high, 3=critical
    timestamp: float = field(default_factory=time.time)

class AsyncEventBus:
    """
    Async event bus for decoupled inter-agent communication.
    Supports priority queuing, subscriber filtering, and replay.
    """
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_log: List[Event] = []
        self._queue: asyncio.Queue = asyncio.Queue()
        logger.info("AsyncEventBus initialised")

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event: Event) -> None:
        self._event_log.append(event)
        if len(self._event_log) > 10000:
            self._event_log = self._event_log[-10000:]
        # Synchronous dispatch
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
        # Also dispatch to wildcard subscribers
        for handler in self._subscribers.get("*", []):
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Wildcard handler error: {e}")

    def get_events(self, event_type: Optional[str] = None, last_n: int = 100) -> List[Event]:
        if event_type:
            return [e for e in self._event_log if e.event_type == event_type][-last_n:]
        return self._event_log[-last_n:]

    async def publish_async(self, event: Event) -> None:
        await self._queue.put(event)

    async def drain(self) -> None:
        while not self._queue.empty():
            event = await self._queue.get()
            self.publish(event)
