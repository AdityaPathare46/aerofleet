import os
import spiceypy as spice
import pandas as pd
import numpy as np
from sgp4.api import Satrec, WGS72

class MissionDataLoader:
    def __init__(self, root_dir):
        """
        Initializes the loader with the root directory of the project.
        Expects 'datasets' folder to be present inside root_dir.
        """
        self.root_dir = root_dir
        self.dataset_dir = os.path.join(self.root_dir, "datasets")
        
        # Define specific paths based on your directory structure
        self.spice_dir = os.path.join(self.dataset_dir, "orbital", "SPICE")
        self.tle_dir = os.path.join(self.dataset_dir, "orbital", "TLE")
        self.env_dir = os.path.join(self.dataset_dir, "environment")
        self.sensor_dir = os.path.join(self.dataset_dir, "sensors")

        self.kernels_loaded = False

    def load_spice_kernels(self):
        """
        Loads the critical NASA SPICE kernels required for planetary ephemeris.
        Strategy:
        1. Load Generic Kernels (LSK, PCK)
        2. Load Primary Ephemeris (DE430)
        3. AUTOMATICALLY load all satellite/planetary kernels in the 'satellite' folder.
        """
        try:
            # 1. Load Leap Seconds (LSK)
            lsk_path = os.path.join(self.spice_dir, "lsk", "naif0012.tls.txt")
            spice.furnsh(lsk_path)
            print(f"[INFO] Loaded LSK: {os.path.basename(lsk_path)}")

            # 2. Load Planetary Constants (PCK)
            pck_path = os.path.join(self.spice_dir, "pck", "pck00010.tpc.txt")
            spice.furnsh(pck_path)
            print(f"[INFO] Loaded PCK: {os.path.basename(pck_path)}")

            # 3. Load Primary Planetary Ephemeris (BSP)
            bsp_path = os.path.join(self.spice_dir, "planetary_ephemeris", "de430.bsp")
            spice.furnsh(bsp_path)
            print(f"[INFO] Loaded Primary BSP: {os.path.basename(bsp_path)}")
            
            # 4. INTELLIGENT LOAD: Scan 'satellite' folder for all other .bsp files
            sat_dir = os.path.join(self.spice_dir, "satellite")
            if os.path.exists(sat_dir):
                loaded_count = 0
                for file in os.listdir(sat_dir):
                    if file.endswith(".bsp"):
                        full_path = os.path.join(sat_dir, file)
                        spice.furnsh(full_path)
                        loaded_count += 1
                print(f"[INFO] Automatically loaded {loaded_count} satellite kernels from {os.path.basename(sat_dir)}")
            else:
                print(f"[WARN] Satellite directory not found: {sat_dir}")

            self.kernels_loaded = True
            print("[SUCCESS] All SPICE Kernels initialized.")
            
        except Exception as e:
            print(f"[ERROR] Failed to load SPICE kernels: {e}")

    def get_planet_position(self, target, observer, time_str):
        """
        Returns position [x, y, z] of target relative to observer at a specific UTC time.
        Example: target='MARS', observer='EARTH', time_str='2025-12-01 12:00:00'
        """
        if not self.kernels_loaded:
            self.load_spice_kernels()
            
        # Convert UTC string to Ephemeris Time (ET)
        et = spice.str2et(time_str)
        
        # Compute position (using J2000 frame, no aberration correction for now)
        state, _ = spice.spkpos(target, et, "J2000", "NONE", observer)
        return state # Returns x, y, z in km

    def load_tle_data(self, tle_filename="active.txt"):
        """
        Loads TLE data for LEO propagation.
        """
        tle_path = os.path.join(self.tle_dir, tle_filename)
        satellites = []
        
        try:
            with open(tle_path, 'r') as f:
                lines = f.readlines()
            
            # Simple TLE parser (active.txt usually has 3 lines per sat: Name, Line1, Line2)
            # Adjust logic if file has only 2 lines per sat
            for i in range(0, len(lines), 3): 
                if i+2 < len(lines):
                    name = lines[i].strip()
                    line1 = lines[i+1].strip()
                    line2 = lines[i+2].strip()
                    sat = Satrec.twoline2rv(line1, line2, WGS72)
                    satellites.append({'name': name, 'satrec': sat})
            
            print(f"[INFO] Loaded {len(satellites)} satellites from {tle_filename}")
            return satellites
        except Exception as e:
            print(f"[ERROR] Could not load TLE file: {e}")
            return []

    def load_solar_data(self):
        """
        Loads the space weather data for atmospheric drag calculation.
        """
        # Loading the specific file seen in your screenshots
        sw_path = os.path.join(self.env_dir, "solar", "space_weather_extended.csv")
        try:
            df = pd.read_csv(sw_path)
            print(f"[INFO] Loaded Space Weather Data: {df.shape[0]} records.")
            return df
        except Exception as e:
            print(f"[ERROR] Could not load solar data: {e}")
            return None

# --- TESTING BLOCK ---
if __name__ == "__main__":
    # DYNAMIC PATH FIX: 
    # 1. Get the absolute path of this script (src/data_loader.py)
    current_script_path = os.path.abspath(__file__)
    
    # 2. Go up one level to find the 'src' folder
    src_dir = os.path.dirname(current_script_path)
    
    # 3. Go up another level to find the Project Root (SpaceMissionArchitect)
    project_root = os.path.dirname(src_dir)
    
    print(f"[DEBUG] Detected Project Root: {project_root}")
    
    # Initialize the loader with the dynamically found root
    loader = MissionDataLoader(project_root)
    
    print("-" * 30)
    print("1. Testing SPICE Kernels...")
    loader.load_spice_kernels()
    try:
        # Test Mars position lookup
        mars_pos = loader.get_planet_position("MARS", "EARTH", "2025-12-30 12:00:00")
        print(f"   [RESULT] Mars Position (km): {mars_pos}")
    except Exception as e:
        print(f"   [FAIL] SPICE Query failed: {e}")

    print("-" * 30)
    print("2. Testing TLE Loader...")
    loader.load_tle_data("active.txt")
    
    print("-" * 30)
    print("3. Testing Solar Data...")
    loader.load_solar_data()
    print("-" * 30)