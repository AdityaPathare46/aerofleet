"""
ChromaDB-backed persistent memory store for Space Mission Architect agents.

Every agent failure (and the correction that fixed it) is stored here.
On restart, agents query this store for relevant past learnings before
entering any debate or scenario run.
"""

import uuid
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from agent_memory.schemas import MemoryRecord, MemoryOutcome

logger = logging.getLogger(__name__)

# Default persistent storage path — lives inside the project directory
_DEFAULT_CHROMA_PATH = Path(__file__).parent.parent / "agent_memory" / "chroma_db"


class AgentMemoryStore:
    """
    Persistent vector-backed memory store for all agents.

    Collections:
      - "agent_failures"  : records of failed scenario attempts + corrections
      - "agent_successes" : records of passed scenarios (positive examples)

    Usage:
        store = AgentMemoryStore()
        store.record_failure(record)
        store.record_success(record)
        past = store.retrieve_relevant(agent_id="orbital_dynamics", query="J2 LEO delta-v")
    """

    FAILURE_COLLECTION = "agent_failures"
    SUCCESS_COLLECTION = "agent_successes"
    TOP_K_DEFAULT = 5

    def __init__(self, persist_path: Optional[Path] = None):
        if not CHROMADB_AVAILABLE:
            logger.warning(
                "chromadb not installed. Agent memory is disabled. "
                "Run: pip install chromadb"
            )
            self._client = None
            self._failures = None
            self._successes = None
            return

        path = persist_path or _DEFAULT_CHROMA_PATH
        path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collections
        self._failures = self._client.get_or_create_collection(
            name=self.FAILURE_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        self._successes = self._client.get_or_create_collection(
            name=self.SUCCESS_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"AgentMemoryStore initialized at {path}. "
            f"Failures: {self._failures.count()}, "
            f"Successes: {self._successes.count()}"
        )

    @property
    def is_available(self) -> bool:
        return self._client is not None

    # ─────────────────────────────────────────────────────────────────────
    #  WRITE
    # ─────────────────────────────────────────────────────────────────────

    def record_failure(self, record: MemoryRecord) -> Optional[str]:
        """
        Persist a failure record to ChromaDB.

        Returns the generated chroma_id, or None if store unavailable.
        """
        if not self.is_available:
            return None

        chroma_id = str(uuid.uuid4())
        record.chroma_id = chroma_id

        self._failures.add(
            ids=[chroma_id],
            documents=[record.to_document_text()],
            metadatas=[record.to_chroma_metadata()],
        )

        logger.debug(
            f"Recorded FAILURE: agent={record.agent_id} "
            f"scenario={record.scenario_id} errors={record.error_types}"
        )
        return chroma_id

    def record_success(self, record: MemoryRecord) -> Optional[str]:
        """
        Persist a success record (passing scenario) to ChromaDB.

        Returns the generated chroma_id, or None if store unavailable.
        """
        if not self.is_available:
            return None

        chroma_id = str(uuid.uuid4())
        record.chroma_id = chroma_id

        self._successes.add(
            ids=[chroma_id],
            documents=[record.to_document_text()],
            metadatas=[record.to_chroma_metadata()],
        )

        logger.debug(
            f"Recorded SUCCESS: agent={record.agent_id} "
            f"scenario={record.scenario_id}"
        )
        return chroma_id

    # ─────────────────────────────────────────────────────────────────────
    #  READ
    # ─────────────────────────────────────────────────────────────────────

    def retrieve_relevant(
        self,
        agent_id: str,
        query: str,
        top_k: int = TOP_K_DEFAULT,
        include_successes: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the most semantically relevant past memories for an agent.

        Args:
            agent_id: Filter results to this agent's memories.
            query: Natural language query describing the current situation.
            top_k: Number of memories to retrieve from each collection.
            include_successes: Whether to also include successful memories.

        Returns:
            List of dicts with keys: document, metadata, distance
        """
        if not self.is_available:
            return []

        results = []

        # Query failures (most important — these contain corrections)
        try:
            failure_results = self._failures.query(
                query_texts=[query],
                n_results=min(top_k, max(1, self._failures.count())),
                where={"agent_id": agent_id} if self._failures.count() > 0 else None,
            )
            results.extend(self._format_results(failure_results, "failure"))
        except Exception as exc:
            logger.warning(f"Memory failure query failed: {exc}")

        # Query successes (positive examples)
        if include_successes:
            try:
                success_results = self._successes.query(
                    query_texts=[query],
                    n_results=min(top_k, max(1, self._successes.count())),
                    where={"agent_id": agent_id} if self._successes.count() > 0 else None,
                )
                results.extend(self._format_results(success_results, "success"))
            except Exception as exc:
                logger.warning(f"Memory success query failed: {exc}")

        # Sort by relevance (lower distance = more similar)
        results.sort(key=lambda x: x.get("distance", 1.0))
        return results[:top_k]

    def retrieve_all_for_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve ALL memory records for a specific agent.
        Used for diagnostics and memory inspection.
        """
        if not self.is_available:
            return []

        results = []
        for collection, label in [(self._failures, "failure"), (self._successes, "success")]:
            try:
                raw = collection.get(where={"agent_id": agent_id})
                for doc, meta in zip(raw.get("documents", []), raw.get("metadatas", [])):
                    results.append({"document": doc, "metadata": meta, "type": label})
            except Exception as exc:
                logger.warning(f"retrieve_all_for_agent query failed: {exc}")

        return results

    def get_stats(self) -> Dict[str, int]:
        """Return memory store statistics."""
        if not self.is_available:
            return {"failures": 0, "successes": 0, "available": 0}
        return {
            "failures": self._failures.count(),
            "successes": self._successes.count(),
            "available": 1,
        }

    # ─────────────────────────────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _format_results(chroma_results: Dict, record_type: str) -> List[Dict[str, Any]]:
        """Format raw ChromaDB query results into clean dicts."""
        formatted = []
        docs = chroma_results.get("documents", [[]])[0]
        metas = chroma_results.get("metadatas", [[]])[0]
        distances = chroma_results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            formatted.append({
                "document": doc,
                "metadata": meta,
                "distance": dist,
                "type": record_type,
            })
        return formatted


# Module-level singleton — shared across all agents in a process
_store: Optional[AgentMemoryStore] = None


def get_memory_store() -> AgentMemoryStore:
    """Return the singleton AgentMemoryStore instance."""
    global _store
    if _store is None:
        _store = AgentMemoryStore()
    return _store
