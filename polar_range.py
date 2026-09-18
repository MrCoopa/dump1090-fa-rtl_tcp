#!/usr/bin/env python3
"""
polar_range.py - Polar Reception Range Collector by Altitude
Tracks real-time aircraft positions and generates multi-layer polar range polygons
for ADS-B receivers (readsb / dump1090).

Altitude brackets (default):
  - 10000 ft:  0 - 9,999 ft    (Approach / Low)
  - 20000 ft: 10,000 - 19,999 ft (Mid-low cruise)
  - 30000 ft: 20,000 - 29,999 ft (Mid-high cruise)
  - 40000 ft: 30,000+ ft        (High cruise)
"""

import os
import sys
import time
import math
import json
import signal
import argparse

EARTH_RADIUS_NM = 3440.065  # Nautical miles
EARTH_RADIUS_KM = 6371.0

# 5 Altitude brackets (ceiling in feet)
ALT_BRACKETS = [
    {"alt": 5000, "label": "0 - 4,999 ft", "min": 0, "max": 4999},
    {"alt": 10000, "label": "5,000 - 9,999 ft", "min": 5000, "max": 9999},
    {"alt": 20000, "label": "10,000 - 19,999 ft", "min": 10000, "max": 19999},
    {"alt": 30000, "label": "20,000 - 29,999 ft", "min": 20000, "max": 29999},
    {"alt": 40000, "label": "30,000+ ft", "min": 30000, "max": 999999},
]

def haversine_distance_nm(lat1, lon1, lat2, lon2):
    """Calculate Great Circle distance in nautical miles."""
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    rdlat = math.radians(lat2 - lat1)
    rdlon = math.radians(lon2 - lon1)
    a = (math.sin(rdlat / 2.0) ** 2 +
         math.cos(rlat1) * math.cos(rlat2) * (math.sin(rdlon / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_NM * c

def initial_bearing(lat1, lon1, lat2, lon2):
    """Calculate initial compass bearing from (lat1, lon1) to (lat2, lon2) in degrees 0..359."""
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    rdlon = math.radians(lon2 - lon1)
    y = math.sin(rdlon) * math.cos(rlat2)
    x = (math.cos(rlat1) * math.sin(rlat2) -
         math.sin(rlat1) * math.cos(rlat2) * math.cos(rdlon))
    deg = math.degrees(math.atan2(y, x))
    return int(round((deg + 360.0) % 360.0)) % 360

def destination_point(lat, lon, dist_nm, bearing_deg):
    """Calculate target lat/lon given origin, distance (NM) and bearing (deg)."""
    d_r = dist_nm / EARTH_RADIUS_NM
    b_r = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)

    lat2 = math.asin(math.sin(lat1) * math.cos(d_r) +
                     math.cos(lat1) * math.sin(d_r) * math.cos(b_r))
    lon2 = lon1 + math.atan2(math.sin(b_r) * math.sin(d_r) * math.cos(lat1),
                             math.cos(d_r) - math.sin(lat1) * math.sin(lat2))
    return (round(math.degrees(lat2), 6), round(math.degrees(lon2), 6))

class PolarRangeCollector:
    def __init__(self, data_dir, output_file, persist_file, hours=24.0, lat=None, lon=None, interval=2.0):
        self.data_dir = data_dir
        self.output_file = output_file
        self.persist_file = persist_file
        self.hours = float(hours)
        self.max_age_sec = self.hours * 3600.0
        self.site_lat = lat
        self.site_lon = lon
        self.interval = float(interval)
        self.running = True

        # 4 brackets x 360 degrees
        # grid[bracket_idx][bearing_deg] = {"dist": dist_nm, "lat": lat, "lon": lon, "time": epoch_sec}
        self.grid = [[None for _ in range(360)] for _ in range(len(ALT_BRACKETS))]
        self.load_persisted_state()

    def get_receiver_location(self):
        if self.site_lat is not None and self.site_lon is not None:
            return self.site_lat, self.site_lon

        # Try receiver.json
        rcv_file = os.path.join(self.data_dir, "receiver.json")
        if os.path.isfile(rcv_file):
            try:
                with open(rcv_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "lat" in data and "lon" in data and data["lat"] is not None:
                        self.site_lat = float(data["lat"])
                        self.site_lon = float(data["lon"])
                        print(f"[polar-range] Found receiver location from receiver.json: {self.site_lat}, {self.site_lon}", flush=True)
                        return self.site_lat, self.site_lon
            except Exception:
                pass

        # Try environment variables
        env_lat = os.environ.get("LAT")
        env_lon = os.environ.get("LON")
        if env_lat and env_lon:
            try:
                self.site_lat = float(env_lat)
                self.site_lon = float(env_lon)
                print(f"[polar-range] Using receiver location from environment: {self.site_lat}, {self.site_lon}", flush=True)
                return self.site_lat, self.site_lon
            except ValueError:
                pass

        return None, None

    def load_persisted_state(self):
        if not self.persist_file or not os.path.isfile(self.persist_file):
            return
        try:
            with open(self.persist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            now = time.time()
            count = 0
            if "grid" in data:
                raw_grid = data["grid"]
                if len(raw_grid) == 4 and len(self.grid) == 5:
                    # Seamless migration from 4-bracket to 5-bracket grid
                    for deg in range(360):
                        if raw_grid[0][deg] and (now - raw_grid[0][deg].get("time", 0) <= self.max_age_sec):
                            self.grid[1][deg] = raw_grid[0][deg]  # Seed 5k-10k
                            count += 1
                        if raw_grid[1][deg] and (now - raw_grid[1][deg].get("time", 0) <= self.max_age_sec):
                            self.grid[2][deg] = raw_grid[1][deg]  # 10k-20k
                            count += 1
                        if raw_grid[2][deg] and (now - raw_grid[2][deg].get("time", 0) <= self.max_age_sec):
                            self.grid[3][deg] = raw_grid[2][deg]  # 20k-30k
                            count += 1
                        if raw_grid[3][deg] and (now - raw_grid[3][deg].get("time", 0) <= self.max_age_sec):
                            self.grid[4][deg] = raw_grid[3][deg]  # 30k+
                            count += 1
                else:
                    for b_idx in range(min(len(self.grid), len(raw_grid))):
                        for deg in range(360):
                            entry = raw_grid[b_idx][deg]
                            if entry and (now - entry.get("time", 0) <= self.max_age_sec):
                                self.grid[b_idx][deg] = entry
                                count += 1
            print(f"[polar-range] Restored {count} polar range data points from {self.persist_file}", flush=True)
        except Exception as e:
            print(f"[polar-range] Could not load persisted state: {e}", flush=True)

    def save_persisted_state(self):
        if not self.persist_file:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.persist_file)), exist_ok=True)
            tmp = self.persist_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"saved_at": time.time(), "grid": self.grid}, f)
            os.replace(tmp, self.persist_file)
        except Exception as e:
            print(f"[polar-range] Error saving persist file: {e}", flush=True)

    def update_aircraft(self, now):
        ac_file = os.path.join(self.data_dir, "aircraft.json")
        if not os.path.isfile(ac_file):
            return 0

        try:
            with open(ac_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return 0

        planes = data.get("aircraft", [])
        if not planes:
            return 0

        lat1, lon1 = self.get_receiver_location()
        if lat1 is None or lon1 is None:
            return 0

        updated = 0
        for p in planes:
            # Check position
            lat2 = p.get("lat")
            lon2 = p.get("lon")
            if lat2 is None or lon2 is None:
                continue

            # Check altitude (ft)
            alt = p.get("alt_baro")
            if alt is None or alt == "ground":
                alt = p.get("alt_geom")
            if alt is None or alt == "ground":
                alt = p.get("altitude")
            if alt is None or alt == "ground":
                alt = 0

            try:
                alt = float(alt)
            except (ValueError, TypeError):
                continue

            # Determine altitude bracket index
            b_idx = None
            for idx, brk in enumerate(ALT_BRACKETS):
                if brk["min"] <= alt <= brk["max"]:
                    b_idx = idx
                    break
            if b_idx is None:
                continue

            dist = haversine_distance_nm(lat1, lon1, lat2, lon2)
            if dist < 0.1 or dist > 400.0:
                continue

            bearing = initial_bearing(lat1, lon1, lat2, lon2)
            current = self.grid[b_idx][bearing]

            if current is None or (now - current["time"] > self.max_age_sec) or (dist > current["dist"]):
                self.grid[b_idx][bearing] = {
                    "dist": round(dist, 2),
                    "lat": round(lat2, 6),
                    "lon": round(lon2, 6),
                    "time": now
                }
                updated += 1

        return updated

    def prune_and_build_json(self, now):
        lat1, lon1 = self.get_receiver_location()
        if lat1 is None or lon1 is None:
            return None

        rings = []
        # Sort descending by altitude so outer/highest rings are rendered first in OpenLayers
        sorted_brackets = sorted(enumerate(ALT_BRACKETS), key=lambda x: x[1]["alt"], reverse=True)

        for b_idx, brk in sorted_brackets:
            row = self.grid[b_idx]
            # Collect valid points (pruning expired)
            valid_deg_dist = {}
            for deg in range(360):
                entry = row[deg]
                if entry:
                    if (now - entry["time"]) <= self.max_age_sec:
                        valid_deg_dist[deg] = (entry["dist"], entry["lat"], entry["lon"])
                    else:
                        row[deg] = None

            if len(valid_deg_dist) < 3:
                # Not enough points yet to form a valid polygon
                continue

            # Interpolate any gaps between known bearings so polygon closes cleanly without shrinking to 0
            known_degs = sorted(valid_deg_dist.keys())
            polygon_points = []

            for i in range(len(known_degs)):
                d_curr = known_degs[i]
                d_next = known_degs[(i + 1) % len(known_degs)]
                dist_curr, lat_curr, lon_curr = valid_deg_dist[d_curr]
                dist_next, lat_next, lon_next = valid_deg_dist[d_next]

                polygon_points.append([lat_curr, lon_curr])

                # Calculate angular gap
                gap = (d_next - d_curr) % 360
                if gap > 1 and gap <= 45:
                    # Linearly interpolate intermediate bearings up to 45 degree gap
                    for step in range(1, gap):
                        frac = step / float(gap)
                        interp_dist = dist_curr + frac * (dist_next - dist_curr)
                        interp_deg = (d_curr + step) % 360
                        p_lat, p_lon = destination_point(lat1, lon1, interp_dist, interp_deg)
                        polygon_points.append([p_lat, p_lon])

            if len(polygon_points) >= 3:
                rings.append({
                    "alt": brk["alt"],
                    "label": brk["label"],
                    "points": polygon_points
                })

        return {
            "type": "polar_range",
            "hours": self.hours,
            "generated": int(now),
            "rings": rings
        }

    def write_output_json(self, data):
        if not data or not self.output_file:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.output_file)), exist_ok=True)
            tmp = self.output_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self.output_file)
        except Exception as e:
            print(f"[polar-range] Error writing {self.output_file}: {e}", flush=True)

    def run(self):
        print(f"[polar-range] Starting polar range collector daemon...", flush=True)
        print(f"[polar-range] Output: {self.output_file}, Persist: {self.persist_file}, Window: {self.hours}h", flush=True)

        last_write = 0
        last_persist = 0

        while self.running:
            now = time.time()
            self.update_aircraft(now)

            # Export JSON every 15 seconds
            if now - last_write >= 15.0:
                data = self.prune_and_build_json(now)
                if data:
                    self.write_output_json(data)
                last_write = now

            # Save persistence state every 5 minutes
            if now - last_persist >= 300.0:
                self.save_persisted_state()
                last_persist = now

            time.sleep(self.interval)

        # On shutdown, save state and write output
        print("[polar-range] Saving state and exiting...", flush=True)
        self.save_persisted_state()
        data = self.prune_and_build_json(time.time())
        if data:
            self.write_output_json(data)

def test_collector():
    """Self-test with dummy aircraft data."""
    import tempfile, shutil
    tmpdir = tempfile.mkdtemp(prefix="polar_test_")
    try:
        data_dir = os.path.join(tmpdir, "adsb")
        os.makedirs(data_dir, exist_ok=True)

        site_lat, site_lon = 50.0, 8.5  # Frankfurt approx
        out_file = os.path.join(data_dir, "polar_range.json")
        persist_file = os.path.join(data_dir, "polar_persist.json")

        collector = PolarRangeCollector(
            data_dir=data_dir,
            output_file=out_file,
            persist_file=persist_file,
            hours=24.0,
            lat=site_lat,
            lon=site_lon
        )

        # Generate fake aircraft at various altitudes and bearings
        aircraft = []
        for deg in range(0, 360, 15):
            # Low altitude (5,000 ft) at 30 NM
            p_lat, p_lon = destination_point(site_lat, site_lon, 30.0, deg)
            aircraft.append({"hex": f"low_{deg:03d}", "lat": p_lat, "lon": p_lon, "alt_baro": 5000})

            # Mid altitude (25,000 ft) at 90 NM
            p_lat2, p_lon2 = destination_point(site_lat, site_lon, 90.0, deg)
            aircraft.append({"hex": f"mid_{deg:03d}", "lat": p_lat2, "lon": p_lon2, "alt_baro": 25000})

            # High altitude (38,000 ft) at 160 NM
            p_lat3, p_lon3 = destination_point(site_lat, site_lon, 160.0, deg)
            aircraft.append({"hex": f"hi_{deg:03d}", "lat": p_lat3, "lon": p_lon3, "alt_baro": 38000})

        ac_file = os.path.join(data_dir, "aircraft.json")
        with open(ac_file, "w", encoding="utf-8") as f:
            json.dump({"now": time.time(), "aircraft": aircraft}, f)

        updated = collector.update_aircraft(time.time())
        res = collector.prune_and_build_json(time.time())
        collector.write_output_json(res)
        collector.save_persisted_state()

        assert os.path.isfile(out_file), "polar_range.json was not created!"
        assert os.path.isfile(persist_file), "polar_persist.json was not created!"
        with open(out_file, "r") as f:
            j = json.load(f)
            assert len(j.get("rings", [])) >= 3, f"Expected at least 3 rings, got {len(j.get('rings', []))}"
            print(f"Self-test SUCCESS! Generated {len(j['rings'])} rings, points: {[len(r['points']) for r in j['rings']]}")

    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ADS-B Polar Reception Range Collector by Altitude")
    parser.add_argument("--data-dir", default="/run/adsb-data", help="Directory containing aircraft.json and receiver.json")
    parser.add_argument("--output", default="/run/adsb-data/polar_range.json", help="Path to output polar_range.json")
    parser.add_argument("--persist", default="/var/lib/collectd/rrd/polar_range_state.json", help="Path to persist state file")
    parser.add_argument("--hours", type=float, default=float(os.environ.get("POLAR_RANGE_HOURS", "24.0")), help="Rolling hours window")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    parser.add_argument("--lat", type=float, default=None, help="Receiver latitude")
    parser.add_argument("--lon", type=float, default=None, help="Receiver longitude")
    parser.add_argument("--test", action="store_true", help="Run self-test and exit")

    args = parser.parse_args()

    if args.test:
        test_collector()
        sys.exit(0)

    collector = PolarRangeCollector(
        data_dir=args.data_dir,
        output_file=args.output,
        persist_file=args.persist,
        hours=args.hours,
        lat=args.lat,
        lon=args.lon,
        interval=args.interval
    )

    def handle_signal(sig, frame):
        collector.running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    collector.run()
