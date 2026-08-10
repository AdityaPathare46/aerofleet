"""
Data loader for SPICE kernels, TLE data, and environmental datasets.

Provides access to:
- NASA SPICE planetary ephemeris
- Two-Line Element (TLE) satellite data
- Space weather and environmental data
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np

try:
    import spiceypy as spice
    SPICE_AVAILABLE = True
except ImportError:
    SPICE_AVAILABLE = False

try:
    from sgp4.api import Satrec, WGS72
    SGP4_AVAILABLE = True
except ImportError:
    SGP4_AVAILABLE = False

from aerofleet.utils.logging import get_logger
from aerofleet.utils.config import get_config
from aerofleet.utils.exceptions import (
    SPICEKernelError,
    ResourceNotFoundError
)

logger = get_logger(__name__)


class MissionDataLoader:
    """Loads and manages mission data including SPICE kernels and TLE files."""
    
    def __init__(self, root_dir: Optional[Path] = None):
        """
        Initialize the data loader.
        
        Args:
            root_dir: Project root directory. If None, uses config.
        """
        config = get_config()
        
        if root_dir is None:
            self.root_dir = config.paths.project_root
        else:
            self.root_dir = Path(root_dir)
        
        self.dataset_dir = self.root_dir / "datasets"
        self.spice_dir = self.dataset_dir / "orbital" / "SPICE"
        self.tle_dir = self.dataset_dir / "orbital" / "TLE"
        self.env_dir = self.dataset_dir / "environment"
        self.sensor_dir = self.dataset_dir / "sensors"
        
        self.kernels_loaded = False
        
        logger.info(
            "Initialized data loader",
            extra={"root_dir": str(self.root_dir)}
        )
    
    def load_spice_kernels(self) -> None:
        """
        Load NASA SPICE kernels for planetary ephemeris.
        
        Loads:
        1. Leap seconds kernel (LSK)
        2. Planetary constants kernel (PCK)
        3. Primary planetary ephemeris (DE430 BSP)
        4. All satellite kernels
        
        Raises:
            SPICEKernelError: If kernel loading fails
        """
        if not SPICE_AVAILABLE:
            raise SPICEKernelError("spiceypy not installed. Install with: pip install spiceypy")
        
        if self.kernels_loaded:
            logger.debug("SPICE kernels already loaded")
            return
        
        try:
            # 1. Leap Seconds Kernel
            lsk_path = self.spice_dir / "lsk" / "naif0012.tls.txt"
            if not lsk_path.exists():
                raise SPICEKernelError(f"LSK kernel not found: {lsk_path}")
            spice.furnsh(str(lsk_path))
            logger.info(f"Loaded LSK: {lsk_path.name}")
            
            # 2. Planetary Constants Kernel
            pck_path = self.spice_dir / "pck" / "pck00010.tpc.txt"
            if not pck_path.exists():
                raise SPICEKernelError(f"PCK kernel not found: {pck_path}")
            spice.furnsh(str(pck_path))
            logger.info(f"Loaded PCK: {pck_path.name}")
            
            # 3. Primary Planetary Ephemeris
            bsp_path = self.spice_dir / "planetary_ephemeris" / "de430.bsp"
            if not bsp_path.exists():
                raise SPICEKernelError(f"BSP kernel not found: {bsp_path}")
            spice.furnsh(str(bsp_path))
            logger.info(f"Loaded primary BSP: {bsp_path.name}")
            
            # 4. Satellite Kernels (auto-discover)
            sat_dir = self.spice_dir / "satellite"
            if sat_dir.exists():
                loaded_count = 0
                for file in sat_dir.glob("*.bsp"):
                    spice.furnsh(str(file))
                    loaded_count += 1
                logger.info(f"Loaded {loaded_count} satellite kernels")
            else:
                logger.warning(f"Satellite directory not found: {sat_dir}")
            
            self.kernels_loaded = True
            logger.info("All SPICE kernels initialized successfully")
            
        except Exception as e:
            raise SPICEKernelError(f"Failed to load SPICE kernels: {e}") from e
    
    def get_planet_position(
        self,
        target: str,
        observer: str,
        time_str: str
    ) -> np.ndarray:
        """
        Get position of target relative to observer at specified time.
        
        Args:
            target: Target body name (e.g., 'MARS', 'JUPITER')
            observer: Observer body name (e.g., 'EARTH', 'SUN')
            time_str: UTC time string (e.g., '2025-12-01 12:00:00')
        
        Returns:
            Position vector [x, y, z] in km
        
        Raises:
            SPICEKernelError: If SPICE query fails
        """
        if not self.kernels_loaded:
            self.load_spice_kernels()
        
        try:
            # Convert UTC to Ephemeris Time
            et = spice.str2et(time_str)
            
            # Compute position (J2000 frame, no aberration correction)
            state, _ = spice.spkpos(target, et, "J2000", "NONE", observer)
            
            logger.debug(
                f"Queried position: {target} relative to {observer}",
                extra={"time": time_str, "position_km": state.tolist()}
            )
            
            return state
            
        except Exception as e:
            raise SPICEKernelError(
                f"Failed to query position for {target}: {e}"
            ) from e
    
    def load_tle_data(self, tle_filename: str = "active.txt") -> List[Dict]:
        """
        Load Two-Line Element (TLE) data for satellite propagation.
        
        Args:
            tle_filename: Name of TLE file in the TLE directory
        
        Returns:
            List of satellite dictionaries with 'name' and 'satrec' keys
        
        Raises:
            ResourceNotFoundError: If TLE file not found
        """
        if not SGP4_AVAILABLE:
            logger.warning("sgp4 not installed. TLE loading unavailable.")
            return []
        
        tle_path = self.tle_dir / tle_filename
        
        if not tle_path.exists():
            raise ResourceNotFoundError(
                f"TLE file not found: {tle_path}",
                resource_type="tle_file",
                resource_id=tle_filename
            )
        
        satellites = []
        
        try:
            with open(tle_path, 'r') as f:
                lines = f.readlines()
            
            # Parse TLE format (3 lines per satellite: name, line1, line2)
            for i in range(0, len(lines), 3):
                if i + 2 < len(lines):
                    name = lines[i].strip()
                    line1 = lines[i + 1].strip()
                    line2 = lines[i + 2].strip()
                    
                    sat = Satrec.twoline2rv(line1, line2, WGS72)
                    satellites.append({'name': name, 'satrec': sat})
            
            logger.info(f"Loaded {len(satellites)} satellites from {tle_filename}")
            return satellites
            
        except Exception as e:
            logger.error(f"Failed to parse TLE file: {e}")
            return []
    
    def load_solar_data(self) -> Optional[pd.DataFrame]:
        """
        Load space weather data for atmospheric drag calculations.
        
        Returns:
            DataFrame with space weather parameters, or None if unavailable
        """
        sw_path = self.env_dir / "solar" / "space_weather_extended.csv"
        
        if not sw_path.exists():
            logger.warning(f"Space weather data not found: {sw_path}")
            return None
        
        try:
            df = pd.read_csv(sw_path)
            logger.info(f"Loaded space weather data: {len(df)} records")
            return df
        except Exception as e:
            logger.error(f"Failed to load solar data: {e}")
            return None
