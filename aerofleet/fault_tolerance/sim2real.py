"""Sim2Real transfer layer with domain randomization and uncertainty injection."""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any, Dict, List
import numpy as np
logger = logging.getLogger(__name__)

@dataclass
class SimDomain:
    gravity_noise_pct: float = 0.01
    sensor_noise_std: float = 0.02
    actuator_delay_ms: float = 10.0
    atmospheric_drag_variation_pct: float = 0.05
    magnetic_field_variation_pct: float = 0.03

class Sim2RealTransfer:
    """
    Domain randomization for Sim2Real transfer.
    Injects calibrated noise into simulation observations
    to bridge the sim-to-real gap for policy deployment.
    """
    def __init__(self, seed: int = 42) -> None:
        self._rng = np.random.default_rng(seed)
        logger.info("Sim2RealTransfer initialised")

    def randomize_domain(self, base_domain: SimDomain, n_variants: int = 10) -> List[SimDomain]:
        """Generate n_variants randomised domain configurations."""
        variants: List[SimDomain] = []
        for _ in range(n_variants):
            variants.append(SimDomain(
                gravity_noise_pct=float(self._rng.uniform(0.0, base_domain.gravity_noise_pct * 2)),
                sensor_noise_std=float(self._rng.uniform(0.0, base_domain.sensor_noise_std * 2)),
                actuator_delay_ms=float(self._rng.uniform(0, base_domain.actuator_delay_ms * 2)),
                atmospheric_drag_variation_pct=float(self._rng.uniform(
                    0, base_domain.atmospheric_drag_variation_pct * 2)),
                magnetic_field_variation_pct=float(self._rng.uniform(
                    0, base_domain.magnetic_field_variation_pct * 2)),
            ))
        return variants

    def inject_uncertainty(self, observation: np.ndarray, domain: SimDomain) -> np.ndarray:
        """Apply domain noise to a simulation observation vector."""
        noise = self._rng.normal(0, domain.sensor_noise_std, size=observation.shape)
        return observation + noise

    def calibrate_policy(
        self,
        sim_performance: float,
        real_performance: float,
    ) -> Dict[str, float]:
        """Estimate Sim2Real gap and recommend calibration parameters."""
        gap = abs(sim_performance - real_performance)
        return {
            "sim_performance": round(sim_performance, 4),
            "real_performance": round(real_performance, 4),
            "sim2real_gap": round(gap, 4),
            "recommended_noise_std": round(gap * 0.5, 4),
            "recommended_domain_variants": max(10, int(gap * 100)),
        }
