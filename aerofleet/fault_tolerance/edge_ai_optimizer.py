"""Edge AI Optimizer — quantized lightweight inference for onboard deployment."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
import numpy as np
logger = logging.getLogger(__name__)

@dataclass
class EdgeInferenceResult:
    output: Any
    latency_ms: float
    quantization_bits: int
    compute_mode: str   # "FULL" | "QUANTIZED_8BIT" | "QUANTIZED_4BIT" | "RULE_BASED"
    energy_estimate_mj: float

class EdgeAIOptimizer:
    """
    Selects inference mode based on available compute budget.
    Green zone: full inference.
    Yellow zone: 8-bit quantization.
    Red zone: 4-bit or rule-based fallback.
    """
    def __init__(self, power_budget_w: float = 50.0) -> None:
        self.power_budget_w = power_budget_w
        logger.info(f"EdgeAIOptimizer: power_budget={power_budget_w}W")

    def infer(
        self,
        model_fn: Callable,
        inputs: np.ndarray,
        energy_zone: str = "GREEN",
    ) -> EdgeInferenceResult:
        import time
        t0 = time.perf_counter()

        if energy_zone == "GREEN":
            result = model_fn(inputs)
            bits = 32
            mode = "FULL"
        elif energy_zone == "YELLOW":
            q_inputs = self._quantize(inputs, bits=8)
            result = model_fn(q_inputs)
            bits = 8
            mode = "QUANTIZED_8BIT"
        else:  # RED zone
            result = self._rule_based_fallback(inputs)
            bits = 4
            mode = "RULE_BASED"

        latency_ms = (time.perf_counter() - t0) * 1000
        energy_mj = latency_ms * self.power_budget_w * 0.001  # E = P*t
        return EdgeInferenceResult(
            output=result,
            latency_ms=round(latency_ms, 2),
            quantization_bits=bits,
            compute_mode=mode,
            energy_estimate_mj=round(energy_mj, 4),
        )

    def _quantize(self, x: np.ndarray, bits: int = 8) -> np.ndarray:
        scale = (2 ** bits - 1) / (x.max() - x.min() + 1e-8)
        return np.round(x * scale) / scale

    def _rule_based_fallback(self, inputs: np.ndarray) -> np.ndarray:
        """Ultra-lightweight threshold-based output (housekeeping only)."""
        return (inputs > 0).astype(float)
