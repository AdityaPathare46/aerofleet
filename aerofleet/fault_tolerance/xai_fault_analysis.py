"""
XAI Fault Analysis — LIME-based explainability for anomaly detection.

Provides:
  - LIME (Local Interpretable Model-agnostic Explanations) for fault detections
  - Human-readable interpretation of which telemetry features drove each anomaly
  - Confidence intervals and feature importance rankings
  - Root-cause visualization data (for dashboard rendering)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FeatureContribution:
    feature: str
    value: float
    contribution: float      # +ve = pushed toward anomaly, -ve = toward nominal
    importance: float        # absolute contribution magnitude
    human_readable: str      # e.g. "battery_soc_pct=23.5 (LOW) → anomaly"


@dataclass
class XAIExplanation:
    anomaly_type: Optional[str]
    confidence: float
    top_features: List[FeatureContribution]
    decision_boundary_approx: float   # estimated threshold value for top feature
    counterfactual: Dict[str, float]  # "what would have to change to avoid anomaly"
    human_summary: str                # one-paragraph plain English explanation
    visualization_data: Dict[str, Any] = field(default_factory=dict)


class XAIFaultAnalyzer:
    """
    LIME-based explainability wrapper for fault detection.

    For each anomaly detection:
    1. Generate n_samples perturbations around the anomalous telemetry point.
    2. Query the black-box classifier on each perturbation.
    3. Fit a local linear model (weighted by proximity to original point).
    4. Extract feature coefficients as contribution scores.
    5. Generate human-readable explanations and counterfactuals.

    Reference: Ribeiro et al. (2016) "Why Should I Trust You?" — LIME
    """

    def __init__(
        self,
        n_samples: int = 200,
        kernel_width: float = 0.25,
    ) -> None:
        self.n_samples = n_samples
        self.kernel_width = kernel_width
        logger.info(f"XAIFaultAnalyzer: n_samples={n_samples}, kernel_width={kernel_width}")

    def explain(
        self,
        telemetry: Dict[str, float],
        classifier: Callable[[Dict[str, float]], Tuple[Optional[str], float]],
        anomaly_type: Optional[str] = None,
        confidence: float = 0.0,
    ) -> XAIExplanation:
        """
        Generate LIME explanation for a fault detection.

        Parameters
        ----------
        telemetry : telemetry dict (feature_name → value)
        classifier : callable that takes a telemetry dict and returns (fault_type, confidence)
        anomaly_type : pre-computed fault type (for display purposes)
        confidence : pre-computed confidence score
        """
        numeric_keys = [k for k, v in telemetry.items() if isinstance(v, (int, float))]
        if not numeric_keys:
            return self._empty_explanation(anomaly_type, confidence)

        x_original = np.array([float(telemetry[k]) for k in numeric_keys])

        # Step 1: Generate perturbations in neighbourhood of x
        noise = np.random.normal(0, self.kernel_width, size=(self.n_samples, len(numeric_keys)))
        perturbations = x_original + noise * (np.abs(x_original) + 1e-6)

        # Step 2: Query classifier on perturbations
        labels = np.zeros(self.n_samples)
        for i, perturb in enumerate(perturbations):
            perturb_dict = {k: float(perturb[j]) for j, k in enumerate(numeric_keys)}
            _, conf = classifier(perturb_dict)
            labels[i] = conf

        # Step 3: Compute proximity weights (Gaussian kernel)
        dists = np.linalg.norm(perturbations - x_original, axis=1)
        weights = np.exp(-dists**2 / (2 * self.kernel_width**2))

        # Step 4: Fit weighted linear model (closed-form WLS)
        X_aug = np.column_stack([perturbations, np.ones(self.n_samples)])
        W = np.diag(weights)
        try:
            coeffs = np.linalg.lstsq(W @ X_aug, W @ labels, rcond=None)[0]
            feature_coeffs = coeffs[:len(numeric_keys)]
        except np.linalg.LinAlgError:
            feature_coeffs = np.zeros(len(numeric_keys))

        # Step 5: Build feature contributions
        contributions: List[FeatureContribution] = []
        for j, key in enumerate(numeric_keys):
            val = float(telemetry[key])
            contrib = float(feature_coeffs[j]) * val
            contributions.append(FeatureContribution(
                feature=key,
                value=round(val, 4),
                contribution=round(contrib, 5),
                importance=round(abs(contrib), 5),
                human_readable=self._humanise(key, val, contrib),
            ))

        contributions.sort(key=lambda c: c.importance, reverse=True)
        top = contributions[:5]

        # Counterfactual: what value would neutralise the top feature's contribution?
        counterfactual: Dict[str, float] = {}
        if top and top[0].contribution > 0:
            target_val = float(x_original[numeric_keys.index(top[0].feature)]) * 0.5
            counterfactual[top[0].feature] = round(target_val, 3)

        # Decision boundary approximation
        top_key = top[0].feature if top else None
        db_approx = 0.0
        if top_key and top_key in numeric_keys:
            idx = numeric_keys.index(top_key)
            db_approx = float(x_original[idx]) * (1 - self.kernel_width)

        summary = self._generate_summary(anomaly_type, confidence, top)

        viz_data = {
            "feature_names": [c.feature for c in top],
            "importances": [c.importance for c in top],
            "contributions": [c.contribution for c in top],
            "values": [c.value for c in top],
        }

        return XAIExplanation(
            anomaly_type=anomaly_type,
            confidence=confidence,
            top_features=top,
            decision_boundary_approx=round(db_approx, 3),
            counterfactual=counterfactual,
            human_summary=summary,
            visualization_data=viz_data,
        )

    def _humanise(self, key: str, value: float, contribution: float) -> str:
        direction = "→ ANOMALY" if contribution > 0 else "→ nominal"
        thresholds = {
            "battery_soc_pct": (30, "LOW"),
            "battery_voltage_v": (22, "LOW"),
            "reaction_wheel_speed_rpm": (1000, "LOW"),
            "peak_temp_c": (85, "HIGH"),
            "link_margin_db": (3, "LOW"),
        }
        label = ""
        if key in thresholds:
            threshold, severity = thresholds[key]
            if (severity == "LOW" and value < threshold) or (severity == "HIGH" and value > threshold):
                label = f" ({severity})"
        return f"{key}={value:.2f}{label} {direction}"

    def _generate_summary(
        self,
        anomaly_type: Optional[str],
        confidence: float,
        features: List[FeatureContribution],
    ) -> str:
        if not anomaly_type:
            return "No anomaly detected. System appears nominal."
        top_f = features[0].human_readable if features else "unknown feature"
        second_f = features[1].human_readable if len(features) > 1 else ""
        s = (
            f"Anomaly detected: {anomaly_type} (confidence: {confidence:.0%}). "
            f"Primary driver: {top_f}. "
        )
        if second_f:
            s += f"Secondary driver: {second_f}. "
        s += f"Review affected subsystems and consider the recommended corrective action."
        return s

    def _empty_explanation(self, anomaly_type: Optional[str], confidence: float) -> XAIExplanation:
        return XAIExplanation(
            anomaly_type=anomaly_type,
            confidence=confidence,
            top_features=[],
            decision_boundary_approx=0.0,
            counterfactual={},
            human_summary="No numeric telemetry available for LIME analysis.",
        )
