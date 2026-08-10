"""
Scenario Registry — loads and indexes YAML/JSON scenario files.

Discovers all scenario files in the scenarios/ directory tree,
parses them into Scenario dataclasses, and provides filtering/querying.
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict
import yaml

from scenario_engine.schemas import Scenario, ScenarioType, ScenarioDifficulty, scenario_from_dict

logger = logging.getLogger(__name__)

_SCENARIOS_ROOT = Path(__file__).parent / "scenarios"


class ScenarioRegistry:
    """
    Loads all YAML scenario files from the scenarios/ directory.

    Supports filtering by type, difficulty, tags, and ID.
    """

    def __init__(self, scenarios_root: Optional[Path] = None):
        self._root = scenarios_root or _SCENARIOS_ROOT
        self._scenarios: Dict[str, Scenario] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Recursively discover and load all .yaml/.json scenario files."""
        if not self._root.exists():
            logger.warning(f"Scenarios root not found: {self._root}")
            return

        count = 0
        errors = 0
        for path in sorted(self._root.rglob("*.yaml")):
            # Skip macOS AppleDouble metadata files
            if path.name.startswith("._"):
                continue
            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
                if not data or "id" not in data:
                    logger.warning(f"Skipping invalid scenario file (no 'id'): {path}")
                    continue
                scenario = scenario_from_dict(data)
                if not scenario.enabled:
                    continue
                self._scenarios[scenario.id] = scenario
                count += 1
            except Exception as exc:
                logger.error(f"Failed to load scenario {path}: {exc}")
                errors += 1

        logger.info(
            f"ScenarioRegistry: loaded {count} scenarios "
            f"({errors} errors) from {self._root}"
        )

    # ─────────────────────────────────────────────────────────────────────
    #  QUERY
    # ─────────────────────────────────────────────────────────────────────

    def get_all(self) -> List[Scenario]:
        """Return all loaded scenarios."""
        return list(self._scenarios.values())

    def get_by_id(self, scenario_id: str) -> Optional[Scenario]:
        """Return a specific scenario by ID."""
        return self._scenarios.get(scenario_id)

    def get_by_type(self, scenario_type: ScenarioType) -> List[Scenario]:
        """Return all scenarios of a given type (historical/synthetic/edge_case)."""
        return [s for s in self._scenarios.values() if s.scenario_type == scenario_type]

    def get_historical(self) -> List[Scenario]:
        return self.get_by_type(ScenarioType.HISTORICAL)

    def get_synthetic(self) -> List[Scenario]:
        return self.get_by_type(ScenarioType.SYNTHETIC)

    def get_by_difficulty(self, difficulty: ScenarioDifficulty) -> List[Scenario]:
        return [s for s in self._scenarios.values() if s.difficulty == difficulty]

    def get_by_tag(self, tag: str) -> List[Scenario]:
        """Return scenarios that include the given tag."""
        return [s for s in self._scenarios.values() if tag in s.tags]

    def get_by_filter(
        self,
        scenario_type: Optional[ScenarioType] = None,
        difficulty: Optional[ScenarioDifficulty] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Scenario]:
        """Flexible multi-filter query."""
        results = list(self._scenarios.values())
        if scenario_type:
            results = [s for s in results if s.scenario_type == scenario_type]
        if difficulty:
            results = [s for s in results if s.difficulty == difficulty]
        if tags:
            results = [s for s in results if any(t in s.tags for t in tags)]
        return results

    @property
    def total(self) -> int:
        return len(self._scenarios)

    def summary(self) -> Dict:
        """Return registry statistics."""
        hist = len(self.get_historical())
        synth = len(self.get_synthetic())
        return {
            "total": self.total,
            "historical": hist,
            "synthetic": synth,
            "by_difficulty": {
                d.value: len(self.get_by_difficulty(d))
                for d in ScenarioDifficulty
            },
        }
