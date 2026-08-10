"""
real_tools — Production physics wrappers for Space Mission Architect.

Wraps NASA/ESA open-source libraries with graceful fallbacks so the
system stays functional even if a library is missing or the calculation
geometry is degenerate.
"""
from .poliastro_bridge import compute_hohmann_dv, compute_transfer_details
from .space_environment import solar_flux_at_distance, van_allen_dose, debris_density_factor
from .deorbit_calculator import atmospheric_decay_years, deorbit_dv_budget

__all__ = [
    "compute_hohmann_dv",
    "compute_transfer_details",
    "solar_flux_at_distance",
    "van_allen_dose",
    "debris_density_factor",
    "atmospheric_decay_years",
    "deorbit_dv_budget",
]
