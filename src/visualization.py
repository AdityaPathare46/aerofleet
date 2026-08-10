import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import numpy as np

def plot_mission_3d(r1, r2, trajectory_engine, dt_seconds):
    """
    Visualizes the transfer orbit in 3D.
    r1: Departure Position (Earth)
    r2: Arrival Position (Mars)
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # 1. Plot Sun
    ax.scatter([0], [0], [0], color='yellow', s=500, label='Sun')
    
    # 2. Plot Earth (Start)
    ax.scatter([r1[0]], [r1[1]], [r1[2]], color='blue', s=100, label='Earth (Start)')
    
    # 3. Plot Mars (End)
    ax.scatter([r2[0]], [r2[1]], [r2[2]], color='red', s=80, label='Mars (Arrival)')
    
    # 4. Generate Transfer Arc Points (Keplerian Propagation)
    # We use the solved velocity v1 to propagate forward
    v1, _ = trajectory_engine.solve_lambert(r1, r2, dt_seconds)
    
    # Simple Numerical Propagator for Visualization (2-Body)
    mu_sun = 1.32712440018e11
    
    # Simulation steps
    steps = 100
    times = np.linspace(0, dt_seconds, steps)
    
    x, y, z = [], [], []
    
    current_r = r1.copy()
    current_v = v1.copy()
    dt = times[1] - times[0]
    
    for _ in times:
        x.append(current_r[0])
        y.append(current_r[1])
        z.append(current_r[2])
        
        # Basic Euler integration for visualization (Fast)
        r_mag = np.linalg.norm(current_r)
        acc = -mu_sun * current_r / r_mag**3
        
        current_v += acc * dt
        current_r += current_v * dt

    ax.plot(x, y, z, color='white', linestyle='--', linewidth=2, label='Transfer Trajectory')
    
    # Styling
    ax.set_facecolor('black')
    ax.grid(False) 
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    
    # Remove axis text for space look
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    
    plt.legend()
    plt.title(f"Autonomous Mission Plan: Earth -> Mars ({int(dt_seconds/86400)} days)", color='white')
    plt.show()