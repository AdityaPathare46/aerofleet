"""Background worker that runs flight-controller compliance inspections.

Same idiom as aerofleet/agents/incident_forensics_worker.py: a module-level
Optional[asyncio.Task], idempotent start/stop wired into app.py, an internal
asyncio.Queue, and the blocking MAVLink work kept off the event loop via
run_in_executor. Jobs run one at a time — there is one flight controller
and one port.

``HARDWARE_LOCK`` is shared with the motor-test endpoint so an inspection
and a motor test can never hold the MAVLink port at the same time.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Sequence

from aerofleet.data.database import get_db_session
from aerofleet.hardware.compliance_rules import InspectionContext, build_report
from aerofleet.hardware.fc_discovery import (
    MISSION_PLANNER_FORWARDING_HELP,
    SOURCE_MANUAL,
    discover,
)
from aerofleet.hardware.fc_inspector import FCInspectionError, FCInspector, FCSnapshot
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

HARDWARE_LOCK = threading.Lock()


@dataclass
class FCInspectionJob:
    inspection_id: str
    connection: Optional[str]
    context: Dict[str, Any]
    sample_seconds: float = 6.0
    udp_ports: Optional[Sequence[int]] = None
    listen_s: float = 2.0
    drone_id: Optional[str] = None
    city: Optional[str] = None
    requested_by: Optional[str] = None


def new_inspection_id() -> str:
    return f"FCI-{uuid.uuid4().hex[:8].upper()}"


def recompute_report(row) -> Dict[str, Any]:
    """Rebuild ``row.report`` from its snapshot + context + checklist + motor
    tests (the single source of truth — see FCInspection's docstring)."""
    snap = FCSnapshot.from_dict(row.snapshot)
    report = build_report(snap, InspectionContext.from_dict(row.context), row.checklist or {}, row.motor_tests or {})
    row.report = report
    row.verdict = report["verdict"]
    return report


class FCInspectionWorker:
    def __init__(self) -> None:
        self._queue: "asyncio.Queue[FCInspectionJob]" = asyncio.Queue()
        self._running = False
        self.current_inspection_id: Optional[str] = None

    @property
    def busy(self) -> bool:
        return self.current_inspection_id is not None or not self._queue.empty()

    def enqueue(self, job: FCInspectionJob) -> None:
        from aerofleet.data.models.models import FCInspection

        with get_db_session() as db:
            db.add(FCInspection(
                inspection_id=job.inspection_id, status="PENDING", progress=0, stage="Queued",
                requested_connection=job.connection, drone_id=job.drone_id, city=job.city,
                context=job.context, requested_by=job.requested_by, checklist={}, motor_tests={},
            ))
        self._queue.put_nowait(job)
        logger.info(f"[{job.inspection_id}] FC inspection queued ({job.connection or 'auto-detect'})")

    async def run_forever(self) -> None:
        self._running = True
        logger.info("FC inspection worker started")
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            self.current_inspection_id = job.inspection_id
            try:
                await asyncio.get_event_loop().run_in_executor(None, self._run, job)
            finally:
                self.current_inspection_id = None
        logger.info("FC inspection worker stopped")

    def stop(self) -> None:
        self._running = False

    # ─────────────────────────────────────────────────────────────────
    #  Synchronous — runs in the executor thread
    # ─────────────────────────────────────────────────────────────────

    def _run(self, job: FCInspectionJob) -> None:
        with HARDWARE_LOCK:
            try:
                self._inspect(job)
            except Exception as exc:
                logger.error(f"[{job.inspection_id}] FC inspection failed: {exc}")
                self._update(job.inspection_id, status="FAILED", error=str(exc), completed_at=datetime.utcnow(),
                             stage="Failed")

    def _inspect(self, job: FCInspectionJob) -> None:
        iid = job.inspection_id
        self._update(iid, status="RUNNING", started_at=datetime.utcnow(), progress=1, stage="Starting")
        connection, source = job.connection, SOURCE_MANUAL
        if not connection:
            self._update(iid, progress=2, stage="Auto-detecting the flight controller")
            result = discover(udp_ports=job.udp_ports, listen_s=job.listen_s)
            rec = result.recommended
            self._update(iid, discovery=result.to_dict())
            if rec is None:
                message = result.summary
                if not any(c.status == "in_use" for c in result.candidates):
                    message += " " + MISSION_PLANNER_FORWARDING_HELP
                self._update(iid, status="FAILED", error=message, completed_at=datetime.utcnow(), stage="No flight controller found")
                return
            connection, source = rec.connection, rec.source
        self._update(iid, connection=connection, source=source)

        last = {"pct": -1, "stage": ""}

        def progress(pct: int, stage: str) -> None:
            if pct - last["pct"] >= 2 or stage.split(" (")[0] != last["stage"].split(" (")[0]:
                last.update(pct=pct, stage=stage)
                self._update(iid, progress=min(pct, 99), stage=stage)

        inspector = FCInspector(connection, source=source, sample_seconds=job.sample_seconds, progress_cb=progress)
        snapshot = inspector.run()
        self._finalize(iid, snapshot)

    @staticmethod
    def _update(inspection_id: str, **fields: Any) -> None:
        from aerofleet.data.models.models import FCInspection

        with get_db_session() as db:
            row = db.query(FCInspection).filter(FCInspection.inspection_id == inspection_id).first()
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)

    @staticmethod
    def _finalize(inspection_id: str, snapshot: FCSnapshot) -> None:
        from aerofleet.data.models.models import FCInspection

        with get_db_session() as db:
            row = db.query(FCInspection).filter(FCInspection.inspection_id == inspection_id).first()
            if row is None:
                return
            row.snapshot = snapshot.to_dict()
            report = recompute_report(row)
            row.status = "READY"
            row.progress = 100
            row.stage = f"Report ready — verdict {report['verdict']}"
            row.completed_at = datetime.utcnow()
        logger.info(f"[{inspection_id}] FC inspection complete — verdict {report['verdict']}")


_worker: Optional[FCInspectionWorker] = None
_task: Optional[asyncio.Task] = None


def get_fc_inspection_worker() -> FCInspectionWorker:
    global _worker
    if _worker is None:
        _worker = FCInspectionWorker()
    return _worker


def start_background_fc_inspection_worker() -> None:
    global _task
    if _task is None:
        _task = asyncio.create_task(get_fc_inspection_worker().run_forever())


def stop_background_fc_inspection_worker() -> None:
    global _task, _worker
    if _worker is not None:
        _worker.stop()
    # Reset both — the old worker's asyncio.Queue is bound to the closed
    # event loop (same reasoning as incident_forensics_worker.py).
    _task = None
    _worker = None


__all__ = [
    "FCInspectionError", "FCInspectionJob", "FCInspectionWorker", "HARDWARE_LOCK",
    "get_fc_inspection_worker", "new_inspection_id", "recompute_report",
    "start_background_fc_inspection_worker", "stop_background_fc_inspection_worker",
]
