from skyfield.api import load, EarthSatellite, wgs84
from datetime import datetime
import numpy as np
import pandas as pd
import requests
from tqdm import tqdm
from math import acos, degrees
import json  # For CZML

# -------------------------------
# CONFIGURATION
# -------------------------------

start_date = datetime(2025, 4, 22)
end_date = datetime(2025, 6, 22)
time_step_minutes = 10
threshold_km = 1000
MAX_SATELLITES = 10  # Set to None for full run

# Your satellite (500 km circular orbit, 98° inclination)
tle_line1 = "0 YOURSAT"
tle_line2 = "1 62630U 25009X   25156.24144034  .00002459  00000-0  18470-3 0  9997"
tle_line3 = "2 62630  97.5204 235.2933 0004725 355.2338   4.8842 15.03491761 21310"

ts = load.timescale()
your_sat = EarthSatellite(tle_line2, tle_line3, tle_line1, ts)

# -------------------------------
# TIME SAMPLING
# -------------------------------

total_minutes = int((end_date - start_date).total_seconds() / 60)
time_steps = np.arange(0, total_minutes, time_step_minutes)
times = ts.utc(start_date.year, start_date.month, start_date.day, time_steps // 60, time_steps % 60)

your_positions = your_sat.at(times).position.km.T
your_df = pd.DataFrame(your_positions, columns=["x_km", "y_km", "z_km"])
your_df["datetime"] = [t.utc_datetime() for t in times]
your_df.to_csv("your_satellite_trajectory.csv", index=False)
print("✅ Your satellite trajectory generated.")

# -------------------------------
# GENERATE CZML FILE
# -------------------------------

print("🛰️ Generating CZML file for your satellite...")

def km_to_m(km):
    return km * 1000

start_time = your_df["datetime"].iloc[0]
epoch_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

cartographic_positions = []

for idx, row in your_df.iterrows():
    time_offset_sec = (row["datetime"] - start_time).total_seconds()
    
    # Correct usage: get the geocentric position from your_sat.at(times[idx])
    geocentric = your_sat.at(times[idx])
    subpoint = wgs84.subpoint(geocentric)
    
    lat = subpoint.latitude.degrees
    lon = subpoint.longitude.degrees
    alt = km_to_m(subpoint.elevation.km)

    cartographic_positions.extend([time_offset_sec, lon, lat, alt])

czml = [
    {
        "id": "document",
        "name": "Your Satellite",
        "version": "1.0"
    },
    {
        "id": "your_satellite",
        "name": "YourSat",
        "availability": f"{epoch_str}/{your_df['datetime'].iloc[-1].strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "position": {
            "epoch": epoch_str,
            "cartographicDegrees": cartographic_positions
        },
        "path": {
            "material": {
                "solidColor": { "color": { "rgba": [255, 0, 0, 255] } }
            },
            "width": 2,
            "leadTime": 0,
            "trailTime": 1000000
        },
        "label": {
            "text": "YourSat",
            "scale": 0.5,
            "fillColor": { "rgba": [255, 255, 255, 255] },
            "showBackground": True,
            "backgroundColor": { "rgba": [0, 0, 0, 200] },
            "font": "11pt sans-serif"
        }
    }
]

czml_output_file = "your_satellite.czml"
with open(czml_output_file, "w") as f:
    json.dump(czml, f, indent=2)

print(f"✅ CZML file generated: {czml_output_file}")

# -------------------------------
# LOAD TLEs + SATCAT
# -------------------------------

print("🔄 Downloading TLEs...")
tle_url = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
tle_lines = requests.get(tle_url).text.strip().splitlines()

print("🌍 Loading SATCAT...")
satcat_url = "https://celestrak.org/pub/satcat.txt"
satcat_txt = requests.get(satcat_url).text

satcat_country = {}
for line in satcat_txt.splitlines():
    if len(line) < 70:
        continue
    try:
        norad = line[13:18].strip()
        country = line[44:49].strip()
        satcat_country[norad] = country
    except:
        continue

# -------------------------------
# BUILD SATELLITE OBJECTS
# -------------------------------

satellites = []
tle_norad_lookup = []

for i in range(0, len(tle_lines) - 2, 3):
    try:
        name = tle_lines[i].strip()
        line1 = tle_lines[i + 1].strip()
        line2 = tle_lines[i + 2].strip()
        norad_raw = line1.split()[1]
        norad_id = ''.join(filter(str.isdigit, norad_raw)).zfill(5)
        sat = EarthSatellite(line1, line2, name, ts)
        satellites.append(sat)
        tle_norad_lookup.append((norad_id, name, sat))
    except Exception as e:
        print(f"❌ TLE parse error at line {i}: {e}")
        continue

if MAX_SATELLITES:
    tle_norad_lookup = tle_norad_lookup[:MAX_SATELLITES]

print(f"✅ Loaded {len(tle_norad_lookup)} satellites")

# -------------------------------
# CHECK CLOSE APPROACHES
# -------------------------------

eph = load('de421.bsp')
sun = eph['sun']

close_approaches = []

print("📡 Checking for close approaches...")
for norad_id, name, sat in tqdm(tle_norad_lookup, desc="Checking satellites"):
    try:
        other_geo = sat.at(times)
        your_geo = your_sat.at(times)

        other_pos = other_geo.position.km.T
        your_pos = your_geo.position.km.T
        distances = np.linalg.norm(your_pos - other_pos, axis=1)

        other_vel = other_geo.velocity.km_per_s.T
        your_vel = your_geo.velocity.km_per_s.T

        for idx, d in enumerate(distances):
            if d < threshold_km:
                rel_vec = other_vel[idx] - your_vel[idx]
                rel_speed = np.linalg.norm(rel_vec)

                time = times[idx]
                country = satcat_country.get(norad_id, "UNKNOWN")

                sun_pos = sun.at(time).position.km
                your_pos_vec = your_pos[idx]
                other_pos_vec = other_pos[idx]

                your_x, your_y, your_z = your_pos[idx]
                other_x, other_y, other_z = other_pos[idx]

                to_other = other_pos_vec - your_pos_vec
                to_sun = sun_pos - your_pos_vec
                dot = np.dot(to_other, to_sun)
                norm_prod = np.linalg.norm(to_other) * np.linalg.norm(to_sun)
                angle_deg = degrees(acos(dot / norm_prod)) if norm_prod != 0 else 180
                is_you_between_sun_and_target = angle_deg < 30

                your_dist = np.linalg.norm(your_pos_vec)
                in_shadow = np.dot(your_pos_vec, sun_pos - your_pos_vec) < 0 and your_dist < np.linalg.norm(sun_pos)
                is_sunlit = not in_shadow

                your_vx, your_vy, your_vz = your_vel[idx]
                other_vx, other_vy, other_vz = other_vel[idx]
                rel_vx, rel_vy, rel_vz = rel_vec

                close_approaches.append({
                    "datetime": time.utc_datetime(),
                    "sat_name": name,
                    "norad_id": norad_id,
                    "country": country,
                    "distance_km": round(d, 2),
                    "relative_velocity_kms": round(rel_speed, 3),
                    "sunlit": is_sunlit,
                    "you_between_sun_and_target": is_you_between_sun_and_target,
                    "your_pos_x": your_x,
                    "your_pos_y": your_y,
                    "your_pos_z": your_z,
                    "other_pos_x": other_x,
                    "other_pos_y": other_y,
                    "other_pos_z": other_z,
                    "your_vel_x": your_vx,
                    "your_vel_y": your_vy,
                    "your_vel_z": your_vz,
                    "other_vel_x": other_vx,
                    "other_vel_y": other_vy,
                    "other_vel_z": other_vz,
                    "rel_vel_x": rel_vx,
                    "rel_vel_y": rel_vy,
                    "rel_vel_z": rel_vz
                })
    except Exception:
        continue

# -------------------------------
# OUTPUT RESULTS
# -------------------------------

output_file = "close_approaches_output.csv"

if close_approaches:
    df = pd.DataFrame(close_approaches)
    df.to_csv(output_file, index=False)
    print(f"\n✅ Close approaches saved to {output_file}")
    print(df.head())
else:
    print("ℹ️ No close approaches found under threshold.")
