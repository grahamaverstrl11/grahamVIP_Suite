import numpy as np

def mean_to_true_anomaly(M_deg, e, tolerance=1e-8, max_iter=100):
    # Convert degrees to radians
    M = np.radians(M_deg)
    
    # Initial guess for E = M
    E = M if e < 0.8 else np.pi  # Better initial guess for higher e

    # Newton-Raphson iteration to solve Kepler's Equation
    for _ in range(max_iter):
        f = E - e * np.sin(E) - M
        f_prime = 1 - e * np.cos(E)
        delta = -f / f_prime
        E += delta
        if abs(delta) < tolerance:
            break

    # Convert Eccentric Anomaly to True Anomaly
    true_anomaly = 2 * np.arctan2(
        np.sqrt(1 + e) * np.sin(E / 2),
        np.sqrt(1 - e) * np.cos(E / 2)
    )

    # Convert radians to degrees and normalize to [0, 360)
    true_anomaly_deg = np.degrees(true_anomaly) % 360

    return true_anomaly_deg

# Example use
M_deg = 235.2933     # Mean Anomaly in degrees
e = 0.0004725          # Eccentricity

true_anomaly = mean_to_true_anomaly(M_deg, e)
print(f"True Anomaly: {true_anomaly:.6f}°")
