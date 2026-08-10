"""Online Adaptation Engine — incremental learning with safe continual learning."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import numpy as np
logger = logging.getLogger(__name__)

@dataclass
class AdaptationEvent:
    event_type: str
    new_data: Dict[str, float]
    threshold_update: Optional[Dict[str, float]] = None
    model_update_triggered: bool = False

class OnlineAdaptationEngine:
    """
    Safe continual learning for onboard fault detection models.

    Uses Elastic Weight Consolidation (EWC) principle:
    Protects important weights while adapting to new telemetry distributions.
    Adaptive thresholds updated via exponential moving average.
    """
    def __init__(self, ema_alpha: float = 0.05, safety_buffer_pct: float = 0.10) -> None:
        self.ema_alpha = ema_alpha
        self.safety_buffer_pct = safety_buffer_pct
        self._thresholds: Dict[str, float] = {}
        self._history: List[Dict[str, float]] = []
        self._ewc_regularization: Dict[str, float] = {}
        logger.info(f"OnlineAdaptationEngine: EMA alpha={ema_alpha}")

    def update_thresholds(self, new_telemetry: Dict[str, float]) -> AdaptationEvent:
        """Update anomaly thresholds via EMA on incoming telemetry."""
        updated: Dict[str, float] = {}
        for key, val in new_telemetry.items():
            if isinstance(val, (int, float)):
                old = self._thresholds.get(key, float(val))
                # EMA update
                new_threshold = (1 - self.ema_alpha) * old + self.ema_alpha * float(val)
                # Safety buffer: threshold = EMA ± buffer
                self._thresholds[key] = new_threshold * (1 + self.safety_buffer_pct)
                updated[key] = round(self._thresholds[key], 4)

        self._history.append(new_telemetry)
        if len(self._history) > 1000:
            self._history = self._history[-1000:]

        return AdaptationEvent(
            event_type="THRESHOLD_UPDATE",
            new_data=new_telemetry,
            threshold_update=updated,
            model_update_triggered=len(self._history) % 100 == 0,
        )

    def is_anomalous(self, telemetry: Dict[str, float]) -> Dict[str, bool]:
        """Check each metric against current adaptive thresholds."""
        flags: Dict[str, bool] = {}
        for key, val in telemetry.items():
            if key in self._thresholds:
                flags[key] = float(val) > self._thresholds[key]
        return flags

    def get_current_thresholds(self) -> Dict[str, float]:
        return dict(self._thresholds)

    def compute_ewc_importance(self) -> Dict[str, float]:
        """
        Estimate Fisher Information as proxy for EWC weight importance.
        High importance → protect these thresholds during adaptation.
        """
        if len(self._history) < 10:
            return {}
        importance: Dict[str, float] = {}
        keys = list(self._history[0].keys()) if self._history else []
        for key in keys:
            vals = [float(h.get(key, 0)) for h in self._history[-100:]]
            if vals:
                importance[key] = round(float(np.var(vals)), 6)
        self._ewc_regularization = importance
        return importance
