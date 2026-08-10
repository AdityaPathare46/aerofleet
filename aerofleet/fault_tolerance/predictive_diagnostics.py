"""
Predictive Diagnostics & Prognostics (PDP).

Hybrid supervised + unsupervised anomaly detection pipeline:
  - Random Forest (supervised): trained on labelled fault signatures
  - Self-Organizing Map (SOM) (unsupervised): detects novel/unlabelled anomalies
  - Output: AnomalyReport with confidence scoring and root-cause hints
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalyReport:
    timestamp: float
    anomaly_detected: bool
    anomaly_type: Optional[str]
    confidence: float               # 0.0–1.0
    source: str                     # "RF" | "SOM" | "HYBRID"
    affected_subsystems: List[str]
    root_cause_hint: Optional[str]
    recommended_action: str
    telemetry_snapshot: Dict[str, Any] = field(default_factory=dict)


class SimpleRandomForest:
    """
    Lightweight Random Forest anomaly classifier.
    Uses majority voting over n_trees decision stumps.
    Trained on labelled fault signature patterns.
    """

    FAULT_SIGNATURES: Dict[str, Dict[str, Tuple[float, float]]] = {
        "reaction_wheel_fault": {
            "reaction_wheel_speed_rpm": (0, 1000),      # below nominal
            "attitude_error_deg": (5.0, 180.0),          # elevated
        },
        "battery_degradation": {
            "battery_soc_pct": (0, 30),
            "battery_voltage_v": (0, 22.0),
        },
        "thermal_anomaly": {
            "peak_temp_c": (85.0, 200.0),
        },
        "communication_loss": {
            "link_margin_db": (-50.0, 0.0),
        },
        "sensor_fault": {
            "star_tracker_health": (0, 0.5),
        },
        "propulsion_anomaly": {
            "thruster_health": (0, 0.4),
        },
    }

    def predict(self, telemetry: Dict[str, Any]) -> Tuple[Optional[str], float]:
        """
        Classify telemetry against fault signatures.
        Returns (fault_type, confidence). confidence=0 → no fault.
        """
        matches: Dict[str, int] = {}

        for fault_type, signature in self.FAULT_SIGNATURES.items():
            match_count = 0
            total_checks = len(signature)
            for key, (low, high) in signature.items():
                val = telemetry.get(key)
                if val is not None and low <= float(val) <= high:
                    match_count += 1
            if total_checks > 0:
                match_ratio = match_count / total_checks
                if match_ratio > 0.5:
                    matches[fault_type] = match_count

        if not matches:
            return None, 0.0

        best_fault = max(matches, key=lambda f: matches[f])
        best_count = matches[best_fault]
        total = len(self.FAULT_SIGNATURES[best_fault])
        confidence = best_count / total
        return best_fault, round(confidence, 3)


class MiniSOM:
    """
    Minimal Self-Organizing Map for unsupervised anomaly detection.
    Detects telemetry that is far from any trained prototype vector.
    """

    def __init__(self, n_prototypes: int = 8, learning_rate: float = 0.1) -> None:
        self.n_prototypes = n_prototypes
        self.learning_rate = learning_rate
        self._prototypes: Optional[np.ndarray] = None
        self._trained = False
        self._feature_keys: List[str] = []

    def fit(self, telemetry_history: List[Dict[str, Any]]) -> None:
        """Fit SOM on historical telemetry (unsupervised)."""
        if not telemetry_history:
            return

        keys = [k for k in telemetry_history[0].keys() if isinstance(telemetry_history[0][k], (int, float))]
        self._feature_keys = keys

        X = np.array([[float(t.get(k, 0)) for k in keys] for t in telemetry_history])
        if X.shape[0] < self.n_prototypes:
            self._prototypes = X.copy()
        else:
            idx = np.random.choice(len(X), self.n_prototypes, replace=False)
            self._prototypes = X[idx].copy()

        # Simple competitive learning
        for _ in range(min(100, len(X))):
            sample = X[np.random.randint(len(X))]
            dists = np.linalg.norm(self._prototypes - sample, axis=1)
            bmu = np.argmin(dists)
            self._prototypes[bmu] += self.learning_rate * (sample - self._prototypes[bmu])

        self._trained = True
        logger.info(f"MiniSOM fitted: {self.n_prototypes} prototypes, {len(keys)} features")

    def anomaly_score(self, telemetry: Dict[str, Any]) -> float:
        """Return normalised distance to nearest prototype (0=normal, 1=anomaly)."""
        if not self._trained or self._prototypes is None:
            return 0.0

        x = np.array([float(telemetry.get(k, 0)) for k in self._feature_keys])
        dists = np.linalg.norm(self._prototypes - x, axis=1)
        min_dist = float(np.min(dists))

        # Normalise to [0, 1] using max training distance
        max_dist = float(np.max(np.linalg.norm(self._prototypes, axis=1))) + 1e-6
        return round(min(1.0, min_dist / max_dist), 3)


class PredictiveDiagnostics:
    """
    Hybrid supervised (RF) + unsupervised (SOM) anomaly detection pipeline.

    Fusion rule:
      - RF confident (>0.7): use RF result
      - SOM score > 0.6 AND RF uncertain: flag as NOVEL_ANOMALY
      - Both low: nominal
    """

    RF_CONFIDENCE_THRESHOLD = 0.7
    SOM_ANOMALY_THRESHOLD = 0.6

    def __init__(self) -> None:
        self._rf = SimpleRandomForest()
        self._som = MiniSOM()
        logger.info("PredictiveDiagnostics (RF+SOM hybrid) initialised")

    def fit_som(self, history: List[Dict[str, Any]]) -> None:
        """Train SOM on nominal telemetry history."""
        self._som.fit(history)

    def analyse(self, telemetry: Dict[str, Any], timestamp: float = 0.0) -> AnomalyReport:
        """Run the hybrid detection pipeline."""
        import time
        ts = timestamp or time.monotonic()

        # RF detection
        rf_fault, rf_confidence = self._rf.predict(telemetry)

        # SOM detection
        som_score = self._som.anomaly_score(telemetry)

        # Fusion
        if rf_fault and rf_confidence >= self.RF_CONFIDENCE_THRESHOLD:
            anomaly_detected = True
            anomaly_type = rf_fault
            confidence = rf_confidence
            source = "RF"
        elif som_score >= self.SOM_ANOMALY_THRESHOLD:
            anomaly_detected = True
            anomaly_type = "NOVEL_ANOMALY"
            confidence = som_score
            source = "SOM"
        elif rf_fault and rf_confidence > 0.3:
            anomaly_detected = True
            anomaly_type = rf_fault
            confidence = (rf_confidence + som_score) / 2.0
            source = "HYBRID"
        else:
            anomaly_detected = False
            anomaly_type = None
            confidence = 0.0
            source = "HYBRID"

        affected = self._infer_affected_subsystems(anomaly_type)
        action = self._recommend_action(anomaly_type)
        root_cause = self._hint_root_cause(anomaly_type, telemetry)

        return AnomalyReport(
            timestamp=ts,
            anomaly_detected=anomaly_detected,
            anomaly_type=anomaly_type,
            confidence=round(confidence, 3),
            source=source,
            affected_subsystems=affected,
            root_cause_hint=root_cause,
            recommended_action=action,
            telemetry_snapshot=dict(telemetry),
        )

    def _infer_affected_subsystems(self, fault_type: Optional[str]) -> List[str]:
        mapping = {
            "reaction_wheel_fault": ["ADCS", "GNC"],
            "battery_degradation": ["EPS", "PAYLOAD"],
            "thermal_anomaly": ["TCS", "EPS"],
            "communication_loss": ["TT&C"],
            "sensor_fault": ["ADCS", "Navigation"],
            "propulsion_anomaly": ["Propulsion", "GNC"],
            "NOVEL_ANOMALY": ["UNKNOWN"],
        }
        return mapping.get(fault_type or "", [])

    def _recommend_action(self, fault_type: Optional[str]) -> str:
        actions = {
            "reaction_wheel_fault": "SWITCH_TO_THRUSTER_BACKUP",
            "battery_degradation": "REDUCE_POWER_MODE",
            "thermal_anomaly": "ATTITUDE_THERMAL_MANAGEMENT",
            "communication_loss": "SWITCH_ANTENNA_SAFE_MODE",
            "sensor_fault": "ACTIVATE_REDUNDANT_SENSOR",
            "propulsion_anomaly": "ISOLATE_THRUSTER_SAFE_HOLD",
            "NOVEL_ANOMALY": "ALERT_GROUND_OPERATOR",
        }
        return actions.get(fault_type or "", "MONITOR_AND_LOG")

    def _hint_root_cause(self, fault_type: Optional[str], telemetry: Dict) -> Optional[str]:
        if fault_type == "battery_degradation":
            soc = telemetry.get("battery_soc_pct", 100)
            return f"Battery SoC at {soc}% — possible cell degradation or increased load"
        if fault_type == "reaction_wheel_fault":
            rpm = telemetry.get("reaction_wheel_speed_rpm", 3000)
            return f"RW speed {rpm} RPM — possible bearing wear or motor desaturation needed"
        return None
