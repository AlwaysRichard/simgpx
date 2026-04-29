# simgpx

A command-line tool that generates GPX location files for the **Apple iOS Simulator** from KML track files or GPS coordinates.

Use it to simulate realistic location data in Xcode without a physical device — walking a trail, driving a route, or pinning to a single coordinate.

---

## Features

- **KML track → timed GPX** — converts Google KML track files into waypoint-timed GPX files the Simulator can replay
- **GPS coordinate → static GPX** — creates a single-waypoint GPX to pin the Simulator to one location
- **Smart output naming** — reverse geocodes the location via OpenStreetMap to auto-generate a descriptive filename (e.g. `RockyMountainNationalPark_track.gpx`)
- **Flexible velocity control** — presets for walking, hiking, driving, custom speeds, fixed intervals, or total duration
- **Relative path support** — input and output paths resolve from your current directory
- **No dependencies** — pure Python 3.10+, standard library only

---

## Requirements

- Python 3.10 or later
- Internet connection (for reverse geocoding via Nominatim — optional, gracefully falls back)

---

## Installation

```bash
cp simgpx.py /usr/local/bin/simgpx
chmod +x /usr/local/bin/simgpx
```

Verify:

```bash
simgpx --help
```

---

## Usage

```
simgpx [parameters] <input>
```

Input type is auto-detected:

| Input | Mode |
|---|---|
| `file.kml` | KML track → `_track.gpx` |
| `LAT, LON` | GPS coordinate → `_point.gpx` |
| *(no args)* / `-h` / `--help` | Show usage |

---

## Examples

```bash
# KML track — auto-named from reverse geocoding, 1s intervals, starts in 1 minute
simgpx BearLakeHike.kml

# KML with full options
simgpx BearLakeHike.kml name="Bear Lake Hike" start=now+5m velocity=hike

# KML from Desktop, output to exports folder
simgpx ~/Desktop/MyTrip.kml output=~/exports/MyHike

# Drive at 65 km/h starting at a specific time
simgpx route.kml start=2025-07-04T09:30 velocity=drive:65

# Spread the whole track over exactly 2 hours
simgpx route.kml velocity=total:2h

# Single GPS pin
simgpx 40.311200, -105.645900

# Named GPS pin with custom output path
simgpx 40.311200, -105.645900 name="Bear Lake Trailhead" output=~/Desktop/BearLake
```

---

## Parameters

### KML Mode

| Parameter | Description | Default |
|---|---|---|
| `output=` | Output path (`.gpx` appended if missing) | Geocoded name, current directory |
| `name=` | Track name in GPX metadata | Geocoded place name |
| `start=` | When the track begins (UTC+0) | `now+1m` |
| `velocity=` | Playback speed / timing mode | `1s` |

### GPS Mode

| Parameter | Description | Default |
|---|---|---|
| `output=` | Output path (`.gpx` appended if missing) | Geocoded name, current directory |
| `name=` | Waypoint name in GPX | Geocoded place name |

> `start=` and `velocity=` do not apply to GPS point mode.

---

## `start=` Formats

| Format | Meaning |
|---|---|
| `now` | Current time (UTC+0) |
| `now+1m` | 1 minute from now |
| `now+3h5m30s` | 3 hrs 5 min 30 sec from now |
| `12:30` | Today at 12:30 (UTC+0) |
| `2025-07-04T09:30` | Specific datetime (UTC+0) |

---

## `velocity=` Formats

| Format | Meaning |
|---|---|
| `1s` | 1 second interval between each point *(default)* |
| `30s` | 30 second interval between each point |
| `1m30s` | 1 min 30 sec interval between each point |
| `walk` | 5 km/h, distance-proportional timestamps |
| `hike` | 3 km/h, distance-proportional timestamps |
| `drive` | 50 km/h, distance-proportional timestamps |
| `drive:90` | Custom speed in km/h |
| `total:45m` | Spread all points evenly over 45 minutes |
| `total:1h30m` | Spread all points evenly over 1 hr 30 min |

---

## Output Filename Rules

1. `output=` supplied → use it, resolve relative to current directory
2. `output=` omitted, `name=` supplied → CamelCase the name → e.g. `BearLakeHike_track.gpx`
3. Both omitted → reverse geocode → e.g. `RockyMountainNationalPark_track.gpx`
4. Geocoding fails → `output_track.gpx` or `output_point.gpx`

---

## GPX Output Format

### KML Track

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="simgpx"
     xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>Bear Lake Hike</name></metadata>
  <wpt lat="40.31120000" lon="-105.64590000">
    <ele>2846.0</ele>
    <time>2025-07-04T09:30:00Z</time>
  </wpt>
  ...
</gpx>
```

### GPS Point

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="simgpx"
     xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="40.31120000" lon="-105.64590000">
    <name>Bear Lake Trailhead</name>
  </wpt>
</gpx>
```

---

## Using the GPX in Xcode

Load the GPX via **Xcode → Debug → Simulate Location → Add GPX File to Project…**

A Simulator must already be running, or use a physical iPhone launched from Xcode in a debug session.

### Workflow for repeated testing

You do not need unique filenames. Run simgpx to the same output file before each test, then select it in **Debug → Simulate Location** — Xcode picks up the updated file automatically.

```bash
# Re-run to the same file each time
simgpx MyTrip.kml output=test velocity=hike
```

Then in Xcode: **Debug → Simulate Location → test** (already in the list after first add).

### Timing

The Simulator paces playback using the `<time>` deltas between waypoints. Control the pace with `velocity=` when generating the file.

---

## Reverse Geocoding

Location names are resolved via [Nominatim (OpenStreetMap)](https://nominatim.org) — free with no API key required. Requires an internet connection. If geocoding is unavailable the tool falls back to `output_track.gpx` / `output_point.gpx`.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `✗ KML file not found` | Check the path; use `./filename.kml` for files in the current directory |
| Geocoding returns wrong name | Use `name=` to set the name explicitly |
| Simulator doesn't move | Ensure the app calls `startUpdatingLocation()` and location permission is granted in the Simulator |
| Simulator opens Files app | Do not drag & drop — use **Debug → Simulate Location** in Xcode instead |
| Track plays too fast / slow | Adjust `velocity=` — try `hike`, `walk`, or `total:45m` for exact duration |
| All points at the same location | Your KML may contain a Point instead of a LineString — simgpx requires a LineString track |

---

## License

MIT
