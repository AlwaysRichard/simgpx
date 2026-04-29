#!/usr/bin/env python3
"""
simgpx — Simulator GPX Generator
Convert KML tracks or GPS coordinates to GPX files for Apple iOS Simulator
location simulation via Xcode scheme or Simulator Features menu.
"""

import xml.etree.ElementTree as ET
import math
import sys
import os
import re
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta, timezone


# ---------------------------------------------------------------------------
# Usage / Help
# ---------------------------------------------------------------------------

USAGE = """
simgpx — Simulator GPX Generator
Generate GPX location files for the Apple iOS Simulator.

USAGE
  simgpx [parameters] <input>

INPUT (auto-detected)
  file.kml              Google KML track file  → _track.gpx
  LAT, LON              GPS coordinate pair    → _point.gpx

  Example paths: MyTrip.kml  ./Desktop/MyTrip.kml  ../data/route.kml

KML PARAMETERS
  output=<path>         Output file path (.gpx appended if missing)
                        Default: geocoded name in current directory
  name="My Hike"        Track name in GPX metadata
                        Default: geocoded place name
  start=<time>          When the track begins (UTC+0)
                        Default: now+1m
  velocity=<value>      Playback speed / timing mode
                        Default: 1s

GPS PARAMETERS
  output=<path>         Output file path (.gpx appended if missing)
  name="My Office"      Waypoint name in GPX
                        Default: geocoded place name

START= FORMATS
  now                   Current time (UTC+0)
  now+1m                1 minute from now
  now+3h5m30s           3 hrs 5 min 30 sec from now
  12:30                 Today at 12:30 (UTC+0)
  2025-07-04T09:30      Specific datetime (UTC+0)

VELOCITY= FORMATS
  1s                    1 second interval between each point  [default]
  30s                   30 second interval between each point
  1m30s                 1 min 30 sec interval between each point
  walk                  5 km/h, distance-proportional timestamps
  hike                  3 km/h, distance-proportional timestamps
  drive                 50 km/h, distance-proportional timestamps
  drive:90              Custom speed in km/h
  total:45m             Spread all points evenly over 45 minutes
  total:1h30m           Spread all points evenly over 1 hr 30 min

EXAMPLES
  simgpx MyTrip.kml
  simgpx ./Desktop/MyTrip.kml output=./exports/MyHike
  simgpx MyTrip.kml name="Bear Lake Hike" start=now+3m velocity=hike
  simgpx MyTrip.kml start=12:30 velocity=drive:65
  simgpx MyTrip.kml velocity=total:1h30m
  simgpx 32.847197, -96.851772
  simgpx 32.847197, -96.851772 output=MySpot
  simgpx 32.847197, -96.851772 name="My Office" output=./Desktop/MySpot

HOW TO USE IN XCODE / APPLE SIMULATOR

  Option A — Xcode Scheme (recommended):
    Edit Scheme → Run → Options → Core Location
    → Allow Location Simulation → Default Location
    → Add GPX File to Project → select your .gpx
    Run the app — the Simulator replays the track automatically.

  Option B — Simulator Features Menu:
    With app running: Simulator menu → Features → Location → Custom GPX…
    Select your .gpx file to start playback immediately.

  Note: Drag & Drop onto the Simulator window opens the Files app
  instead of triggering location simulation — use Options A or B above.

  Timing: The Simulator paces playback using the <time> deltas between
  waypoints. Smaller gaps = faster playback. To replay, stop and
  re-run the app or re-select via the Features menu.
"""


def show_usage():
    print(USAGE.strip())
    sys.exit(0)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> dict:
    """
    Parse command-line arguments into a dict.
    Handles both key=value params and positional lat/lon coordinates.
    """
    if not argv or argv[0] in ("-h", "--help"):
        show_usage()

    result = {
        "kml": None,
        "lat": None,
        "lon": None,
        "output": None,
        "name": None,
        "start": "now+1m",
        "velocity": "1s",
        "mode": None,  # "kml" or "gps"
    }

    # Collect raw tokens — join the full argv so we can handle "LAT, LON"
    # where the comma may have caused a split
    raw = " ".join(argv)

    # Extract key=value params first, removing them from raw
    kv_pattern = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')
    for m in kv_pattern.finditer(raw):
        key = m.group(1).lower()
        val = m.group(2).strip('"')
        if key in result:
            result[key] = val
    raw_stripped = kv_pattern.sub("", raw).strip()

    # What's left should be either a .kml path or two numbers (lat, lon)
    # Normalise: remove stray commas, collapse whitespace
    leftover = re.sub(r",", " ", raw_stripped).split()

    if not leftover and result["kml"] is None:
        show_usage()

    if result["kml"] is not None:
        result["mode"] = "kml"
    elif len(leftover) == 1 and leftover[0].lower().endswith(".kml"):
        result["kml"] = leftover[0]
        result["mode"] = "kml"
    elif len(leftover) >= 2:
        try:
            result["lat"] = float(leftover[0])
            result["lon"] = float(leftover[1])
            result["mode"] = "gps"
        except ValueError:
            pass
    elif len(leftover) == 1:
        # Could be a kml path without extension guard
        candidate = leftover[0]
        if os.path.isfile(candidate):
            result["kml"] = candidate
            result["mode"] = "kml"

    if result["mode"] is None:
        print("✗ Could not determine input type. Pass a .kml file or LAT, LON coordinates.")
        print("  Run: simgpx --help")
        sys.exit(1)

    return result


# ---------------------------------------------------------------------------
# KML parsing
# ---------------------------------------------------------------------------

def parse_kml_coordinates(kml_path: str) -> list[tuple[float, float, float]]:
    """Return list of (lon, lat, alt) from the first LineString in a KML."""
    kml_path = os.path.expanduser(kml_path)
    if not os.path.isfile(kml_path):
        print(f"✗ KML file not found: {kml_path}")
        sys.exit(1)

    tree = ET.parse(kml_path)
    root = tree.getroot()

    ns_candidates = [
        "http://www.opengis.net/kml/2.2",
        "http://earth.google.com/kml/2.1",
        "http://earth.google.com/kml/2.0",
    ]

    coords_text = None
    for ns in ns_candidates:
        el = root.find(f".//{{{ns}}}coordinates")
        if el is not None and el.text:
            coords_text = el.text.strip()
            break

    if coords_text is None:
        el = root.find(".//coordinates")
        if el is not None and el.text:
            coords_text = el.text.strip()

    if not coords_text:
        print("✗ No <coordinates> element found in KML.")
        sys.exit(1)

    points = []
    for token in coords_text.split():
        parts = token.split(",")
        if len(parts) >= 2:
            lon = float(parts[0])
            lat = float(parts[1])
            alt = float(parts[2]) if len(parts) >= 3 else 0.0
            points.append((lon, lat, alt))

    return points


# ---------------------------------------------------------------------------
# Geo math
# ---------------------------------------------------------------------------

def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def total_track_distance(points: list[tuple[float, float, float]]) -> float:
    total = 0.0
    for i in range(1, len(points)):
        total += haversine_distance(
            points[i-1][1], points[i-1][0],
            points[i][1],   points[i][0]
        )
    return total


def centroid(points: list[tuple[float, float, float]]) -> tuple[float, float]:
    lats = [p[1] for p in points]
    lons = [p[0] for p in points]
    return sum(lats) / len(lats), sum(lons) / len(lons)


# ---------------------------------------------------------------------------
# Reverse geocoding (Nominatim)
# ---------------------------------------------------------------------------

def reverse_geocode(lat: float, lon: float) -> str:
    """
    Returns a human-readable place name via Nominatim.
    Falls back to None on any error.
    """
    url = (
        f"https://nominatim.openstreetmap.org/reverse"
        f"?lat={lat}&lon={lon}&format=json&zoom=10"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "simgpx/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        # Debug: print full Nominatim response
        # print("\n── Nominatim raw response ──")
        # print(json.dumps(data, indent=2))
        # print("────────────────────────────\n")

        # First choice: the name of the OSM object itself
        if data.get("name"):
            return data["name"]

        # Fallback: walk address fields from most to least specific
        addr = data.get("address", {})
        for key in ("leisure", "tourism", "natural", "park", "suburb",
                    "neighbourhood", "village", "town", "city", "county", "state"):
            val = addr.get(key)
            if val:
                return val

        return data.get("display_name", "").split(",")[0]
    except Exception:
        return None


def to_camel_case(name: str) -> str:
    """Convert a place name to CamelCase for use in filenames."""
    parts = re.sub(r"[^a-zA-Z0-9\s]", "", name).split()
    return "".join(w.capitalize() for w in parts if w)


# ---------------------------------------------------------------------------
# start= parser
# ---------------------------------------------------------------------------

def parse_start(start_str: str) -> datetime:
    """
    Parse a start= value into a UTC datetime.
    Formats: now | now+1m | now+3h5m30s | 12:30 | 2025-07-04T09:30
    """
    now = datetime.now(timezone.utc)
    s = start_str.strip().lower()

    if s == "now":
        return now

    # now+1m / now+3h5m30s
    m = re.match(r"now\+(.+)", s)
    if m:
        delta = parse_duration(m.group(1))
        return now + delta

    # HH:MM — today at that time UTC
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        return now.replace(hour=h, minute=mn, second=0, microsecond=0)

    # ISO datetime: 2025-07-04T09:30 or 2025-07-04 09:30
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(start_str.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    print(f"✗ Could not parse start= value: {start_str!r}")
    print("  Valid formats: now  now+1m  now+3h5m  12:30  2025-07-04T09:30")
    sys.exit(1)


def parse_duration(s: str) -> timedelta:
    """Parse a duration string like 1h30m10s into a timedelta."""
    s = s.lower()
    h = int(m.group(1)) if (m := re.search(r"(\d+)h", s)) else 0
    mn = int(m.group(1)) if (m := re.search(r"(\d+)m(?!s)", s)) else 0
    sec = int(m.group(1)) if (m := re.search(r"(\d+)s", s)) else 0
    total = h * 3600 + mn * 60 + sec
    if total == 0:
        print(f"✗ Could not parse duration: {s!r}. Example: 1h30m or 45m or 30s")
        sys.exit(1)
    return timedelta(seconds=total)


# ---------------------------------------------------------------------------
# velocity= parser
# ---------------------------------------------------------------------------

VELOCITY_PRESETS = {
    "walk":  5.0,    # km/h
    "hike":  3.0,
    "drive": 50.0,
}


def parse_velocity(vel_str: str) -> tuple[str, float]:
    """
    Returns (mode, value):
      ("interval", seconds)
      ("speed",    m/s)
      ("total",    seconds)
    """
    s = vel_str.strip().lower()

    # Presets: walk / hike / drive
    if s in VELOCITY_PRESETS:
        return ("speed", VELOCITY_PRESETS[s] * 1000 / 3600)

    # drive:90  → custom km/h
    m = re.match(r"drive:(\d+(?:\.\d+)?)$", s)
    if m:
        kmh = float(m.group(1))
        return ("speed", kmh * 1000 / 3600)

    # total:45m / total:1h30m
    m = re.match(r"total:(.+)$", s)
    if m:
        delta = parse_duration(m.group(1))
        return ("total", delta.total_seconds())

    # Interval: 1s / 30s / 1m30s
    try:
        delta = parse_duration(s)
        return ("interval", delta.total_seconds())
    except SystemExit:
        pass

    print(f"✗ Could not parse velocity= value: {vel_str!r}")
    print("  Examples: 1s  30s  1m30s  walk  hike  drive  drive:90  total:45m  total:1h30m")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Timestamp computation
# ---------------------------------------------------------------------------

def compute_timestamps(
    points: list[tuple[float, float, float]],
    start_dt: datetime,
    mode: str,
    value: float,
) -> list[datetime]:
    n = len(points)

    if mode == "interval":
        return [start_dt + timedelta(seconds=i * value) for i in range(n)]

    # Build cumulative distances
    cum = [0.0]
    for i in range(1, n):
        d = haversine_distance(
            points[i-1][1], points[i-1][0],
            points[i][1],   points[i][0]
        )
        cum.append(cum[-1] + d)
    total = cum[-1]

    if mode == "speed":
        times = [start_dt]
        for i in range(1, n):
            seg = cum[i] - cum[i-1]
            dt_sec = seg / value if value > 0 else 0
            times.append(times[-1] + timedelta(seconds=dt_sec))
        return times

    if mode == "total":
        total_sec = value
        times = []
        for d in cum:
            frac = (d / total) if total > 0 else 0.0
            times.append(start_dt + timedelta(seconds=frac * total_sec))
        return times

    raise ValueError(f"Unknown mode: {mode}")


# ---------------------------------------------------------------------------
# GPX writers
# ---------------------------------------------------------------------------

def resolve_output_path(output_param: str | None, suffix: str, geocode_name: str | None) -> str:
    """
    Determine final output path.
      - output= supplied → use it (relative paths resolved from cwd)
      - otherwise → geocoded CamelCase name + suffix in cwd
      - fallback → output_track.gpx / output_point.gpx in cwd
    """
    if output_param:
        path = os.path.expanduser(output_param)
        if not path.lower().endswith(".gpx"):
            path += ".gpx"
        return path

    if geocode_name:
        base = to_camel_case(geocode_name)
        if base:
            return os.path.join(os.getcwd(), f"{base}{suffix}")

    return os.path.join(os.getcwd(), f"output{suffix}")


def write_track_gpx(
    points: list[tuple[float, float, float]],
    timestamps: list[datetime],
    output_path: str,
    track_name: str,
) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="simgpx"',
        '     xmlns="http://www.topografix.com/GPX/1/1">',
        f'  <metadata><name>{track_name}</name></metadata>',
    ]
    for (lon, lat, alt), ts in zip(points, timestamps):
        time_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        lines.append(f'  <wpt lat="{lat:.8f}" lon="{lon:.8f}">')
        if alt:
            lines.append(f'    <ele>{alt:.1f}</ele>')
        lines.append(f'    <time>{time_str}</time>')
        lines.append('  </wpt>')
    lines.append('</gpx>')

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def write_point_gpx(
    lat: float,
    lon: float,
    output_path: str,
    point_name: str,
) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="simgpx"',
        '     xmlns="http://www.topografix.com/GPX/1/1">',
        f'  <wpt lat="{lat:.8f}" lon="{lon:.8f}">',
        f'    <name>{point_name}</name>',
        '  </wpt>',
        '</gpx>',
    ]

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Main flows
# ---------------------------------------------------------------------------

def run_kml(args: dict) -> None:
    kml_path = os.path.expanduser(args["kml"])
    print(f"\n  Parsing: {kml_path}")
    points = parse_kml_coordinates(kml_path)
    print(f"  Found {len(points)} track points.")

    track_m = total_track_distance(points)
    print(f"  Total distance: {track_m:.0f} m  ({track_m / 1000:.2f} km)")

    # Geocode centroid for name / filename
    clat, clon = centroid(points)
    print(f"  Centroid: {clat:.5f}, {clon:.5f}")
    print("  Reverse geocoding…", end=" ", flush=True)
    geo_name = reverse_geocode(clat, clon)
    print(geo_name or "unavailable")

    place_name = args["name"] or geo_name or "Track"
    out_path = resolve_output_path(args["output"], "_track.gpx", args["name"] or geo_name)

    start_dt = parse_start(args["start"])
    vel_mode, vel_value = parse_velocity(args["velocity"])

    timestamps = compute_timestamps(points, start_dt, vel_mode, vel_value)

    total_sec = (timestamps[-1] - timestamps[0]).total_seconds()
    avg_kmh = (track_m / total_sec * 3.6) if total_sec > 0 else 0

    print(f"\n  Track name      : {place_name}")
    print(f"  Start time      : {start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')} UTC")
    print(f"  Playback        : {total_sec / 60:.1f} min  ({total_sec:.0f} s)")
    print(f"  Average speed   : {avg_kmh:.1f} km/h")

    write_track_gpx(points, timestamps, out_path, place_name)
    print(f"\n  ✓ Written: {out_path}")
    print_simulator_instructions()


def run_gps(args: dict) -> None:
    lat, lon = args["lat"], args["lon"]
    print(f"\n  Coordinate: {lat}, {lon}")
    print("  Reverse geocoding…", end=" ", flush=True)
    geo_name = reverse_geocode(lat, lon)
    print(geo_name or "unavailable")

    place_name = args["name"] or geo_name or "Location"
    out_path = resolve_output_path(args["output"], "_point.gpx", args["name"] or geo_name)

    print(f"\n  Point name : {place_name}")

    write_point_gpx(lat, lon, out_path, place_name)
    print(f"\n  ✓ Written: {out_path}")
    print_simulator_instructions()


def print_simulator_instructions() -> None:
    print()
    print("─" * 60)
    print("HOW TO USE IN XCODE / APPLE SIMULATOR")
    print("─" * 60)
    print()
    print("  Option A — Xcode Scheme (recommended):")
    print("    Edit Scheme → Run → Options → Core Location")
    print("    → Allow Location Simulation → Default Location")
    print("    → Add GPX File to Project → select your .gpx")
    print("    Run the app — the Simulator replays the track automatically.")
    print()
    print("  Option B — Simulator Features Menu:")
    print("    With app running:")
    print("    Simulator menu → Features → Location → Custom GPX…")
    print("    Select your .gpx file to start playback immediately.")
    print()
    print("  ⚠️  Note: Drag & Drop onto the Simulator window opens the")
    print("     Files app instead of triggering location simulation.")
    print("     Use Option A or B above.")
    print()
    print("  ℹ️  The Simulator paces playback using the <time> deltas.")
    print("     Smaller gaps = faster playback.")
    print("     To replay: stop the app and re-run, or re-select via")
    print("     Features → Location → Custom GPX…")
    print("─" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  simgpx — Simulator GPX Generator")
    print("=" * 60)

    args = parse_args(sys.argv[1:])

    if args["mode"] == "kml":
        run_kml(args)
    elif args["mode"] == "gps":
        run_gps(args)
    else:
        show_usage()


if __name__ == "__main__":
    main()