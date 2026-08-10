"""Distributed Recovery Orchestrator — eliminates single point of failure."""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)

@dataclass
class RecoveryNode:
    node_id: str
    role: str   # "PRIMARY" | "BACKUP" | "OBSERVER"
    is_alive: bool = True
    last_heartbeat: float = field(default_factory=time.monotonic)
    managed_faults: List[str] = field(default_factory=list)

class DistributedRecoveryOrchestrator:
    """
    Distributed fault recovery with no single coordinator.
    Uses a Raft-inspired leader election: backup nodes take over if primary
    heartbeat is absent for > heartbeat_timeout_s.
    """
    def __init__(self, heartbeat_timeout_s: float = 30.0) -> None:
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self._nodes: Dict[str, RecoveryNode] = {}
        self._primary: Optional[str] = None
        logger.info("DistributedRecoveryOrchestrator initialised")

    def register_node(self, node_id: str, role: str = "OBSERVER") -> RecoveryNode:
        node = RecoveryNode(node_id=node_id, role=role)
        self._nodes[node_id] = node
        if role == "PRIMARY":
            self._primary = node_id
        return node

    def heartbeat(self, node_id: str) -> None:
        if node_id in self._nodes:
            self._nodes[node_id].last_heartbeat = time.monotonic()
            self._nodes[node_id].is_alive = True

    def check_health(self) -> Dict[str, Any]:
        now = time.monotonic()
        for node in self._nodes.values():
            if now - node.last_heartbeat > self.heartbeat_timeout_s:
                node.is_alive = False

        primary_alive = self._primary and self._nodes.get(self._primary, RecoveryNode("x","x")).is_alive

        if not primary_alive:
            self._elect_new_primary()

        return {
            "primary": self._primary,
            "nodes": {nid: {"role": n.role, "alive": n.is_alive} for nid, n in self._nodes.items()},
        }

    def _elect_new_primary(self) -> None:
        backups = [n for n in self._nodes.values() if n.role == "BACKUP" and n.is_alive]
        if backups:
            new_primary = backups[0]
            new_primary.role = "PRIMARY"
            self._primary = new_primary.node_id
            logger.warning(f"Primary failed. Elected new primary: {new_primary.node_id}")
        else:
            logger.error("No backup nodes available for primary election!")
