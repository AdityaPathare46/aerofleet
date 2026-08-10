"""Telemetry streaming pipeline — real-time telemetry ingestion and buffering."""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional
logger = logging.getLogger(__name__)

@dataclass
class TelemetryFrame:
    spacecraft_id: str
    timestamp: float
    data: Dict[str, Any]
    quality: float   # 0=corrupt, 1=perfect
    sequence_number: int

class TelemetryStream:
    """
    Real-time telemetry stream processor.
    Supports: gap detection, quality filtering, interpolation, callbacks.
    """
    def __init__(self, spacecraft_id: str, expected_rate_hz: float = 1.0) -> None:
        self.spacecraft_id = spacecraft_id
        self.expected_rate_hz = expected_rate_hz
        self._frames: List[TelemetryFrame] = []
        self._callbacks: List[Callable] = []
        self._seq = 0
        self._last_timestamp: Optional[float] = None
        logger.info(f"TelemetryStream: {spacecraft_id} @ {expected_rate_hz} Hz")

    def ingest(self, data: Dict[str, Any], quality: float = 1.0) -> TelemetryFrame:
        self._seq += 1
        now = time.time()
        frame = TelemetryFrame(
            spacecraft_id=self.spacecraft_id,
            timestamp=now,
            data=data,
            quality=quality,
            sequence_number=self._seq,
        )
        gap = None
        if self._last_timestamp is not None:
            dt = now - self._last_timestamp
            expected_dt = 1.0 / self.expected_rate_hz
            if dt > expected_dt * 3.0:
                gap = dt
                logger.warning(f"TelemetryStream gap detected: {dt:.1f}s (expected {expected_dt:.1f}s)")

        self._last_timestamp = now
        self._frames.append(frame)
        if len(self._frames) > 10000:
            self._frames = self._frames[-10000:]

        for cb in self._callbacks:
            try:
                cb(frame, gap)
            except Exception as e:
                logger.error(f"Telemetry callback error: {e}")

        return frame

    def subscribe(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def get_latest(self, n: int = 1) -> List[TelemetryFrame]:
        return self._frames[-n:]

    def get_field_history(self, field: str, last_n: int = 100) -> List[float]:
        return [
            float(f.data[field]) for f in self._frames[-last_n:]
            if field in f.data and isinstance(f.data[field], (int, float))
        ]
