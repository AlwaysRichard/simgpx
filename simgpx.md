# simgpx — Simulator GPX Generator

Generate GPX location files for the Apple iOS Simulator from KML track files or GPS coordinates.

---

## Installation

Copy `simgpx.py` to a directory on your PATH and make it executable:

```bash
cp simgpx.py /usr/local/bin/simgpx
chmod +x /usr/local/bin/simgpx
```

Requires Python 3.10+ (standard library only — no pip installs needed).

---

## Usage

```
simgpx [parameters] <input>
```

The input type is auto-detected:

| Input | Mode |
|---|---|
| `file.kml` | KML track → `_track.gpx` |
| `LAT, LON` | GPS coordinate → `_point.gpx` |
| *(no args)* / `-h` / `--help` | Show this help |

---

## KML Track Mode

Convert a Google KML track file to a timed GPX for Simulator playback.

```bash
simgpx MyTrip.kml
simgpx ./Desktop/MyTrip.kml output=./exports/MyHike
simgpx MyTrip.kml name="Bear Lake Hike" start=now+3m velocity=hike
simgpx MyTrip.kml start=12:30 velocity=drive:65
simgpx MyTrip.kml velocity=total:1h30m
```

### KML Parameters

| Parameter | Description | Default |
|---|---|---|
| `output=` | Output file path (`.gpx` appended if missing). Relative paths resolve from current directory. | Geocoded name in current directory |
| `name=` | Track name written into GPX metadata | Geocoded place name |
| `start=` | When the track begins (UTC+0) | `now+1m` |
| `velocity=` | Playback speed / timing mode | `1s` |

---

## GPS Point Mode

Create a single-waypoint GPX file for pinning the Simulator to one location.

```bash
simgpx 32.847197, -96.851772
simgpx 32.847197, -96.851772 output=MySpot
simgpx 32.847197, -96.851772 name="My Office" output=./Desktop/MySpot
```

### GPS Parameters

| Parameter | Description | Default |
|---|---|---|
| `output=` | Output file path (`.gpx` appended if missing) | Geocoded name in current directory |
| `name=` | Waypoint name written into GPX | Geocoded place name |

> `start=` and `velocity=` do not apply to GPS point mode — the output is a static pin with no timestamps.

---

## `start=` Formats

All times are expressed as UTC+0.

| Format | Meaning |
|---|---|
| `now` | Current time |
| `now+1m` | 1 minute from now |
| `now+3h5m30s` | 3 hrs 5 min 30 sec from now |
| `12:30` | Today at 12:30 UTC+0 |
| `2025-07-04T09:30` | Specific datetime, UTC+0 |

---

## `velocity=` Formats

| Format | Meaning |
|---|---|
| `1s` | 1 second interval between each point *(default)* |
| `30s` | 30 second interval between each point |
| `1m30s` | 1 min 30 sec interval between each point |
| `walk` | 5 km/h, timestamps proportional to segment distance |
| `hike` | 3 km/h, timestamps proportional to segment distance |
| `drive` | 50 km/h, timestamps proportional to segment distance |
| `drive:90` | Custom speed in km/h, distance-proportional |
| `total:45m` | Spread all points evenly over 45 minutes |
| `total:1h30m` | Spread all points evenly over 1 hr 30 min |

### Velocity Presets

| Keyword | Speed |
|---|---|
| `walk` | 5 km/h |
| `hike` | 3 km/h |
| `drive` | 50 km/h |
| `drive:N` | N km/h (any value) |

---

## Output Filename Rules

1. **`output=` supplied** → use it as-is, append `.gpx` if missing, resolve relative to cwd
2. **`output=` omitted, `name=` supplied** → CamelCase the name → e.g. `BearLakeHike_track.gpx` in cwd
3. **Both omitted** → reverse geocode the location → CamelCase place name → e.g. `RockyMountainsNationalPark_track.gpx` in cwd
4. **Geocoding fails** → `output_track.gpx` or `output_point.gpx` in cwd

---

## Reverse Geocoding

- Service: [Nominatim (OpenStreetMap)](https://nominatim.org) — free, no API key required
- KML: geocodes the centroid (average lat/lon of all track points)
- GPS: geocodes the single coordinate
- Name resolution: most specific useful label returned (park, landmark, neighborhood, city — not street number)
- Requires an internet connection; gracefully falls back to `output_track.gpx` / `output_point.gpx` if unavailable

---

## GPX Output Formats

### KML Track Output

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

### GPS Point Output

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="simgpx"
     xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="32.84719700" lon="-96.85177200">
    <name>My Office</name>
  </wpt>
</gpx>
```

---

## Using the GPX File in Xcode / Apple Simulator

### Option A — Xcode Scheme *(recommended)*

This method loads your GPX into the scheme so the Simulator starts replaying immediately when you run the app.

1. In Xcode, go to **Product → Scheme → Edit Scheme…**
2. Select **Run** on the left, then the **Options** tab
3. Under **Core Location**, check **Allow Location Simulation**
4. Set **Default Location** → click the dropdown → **Add GPX File to Project…**
5. Select your `.gpx` file
6. Run the app — the Simulator replays the track automatically

### Option B — Simulator Features Menu

This method lets you trigger playback while the app is already running.

1. Launch your app in the Simulator
2. In the Simulator menu bar: **Features → Location → Custom GPX…**
3. Select your `.gpx` file — playback starts immediately

> **⚠️ Drag & Drop does not work for location simulation.**
> Dragging a `.gpx` file onto the Simulator window opens the **Files** app inside the Simulator instead of triggering location simulation. Use Option A or B above.

### Replay

To replay a track: stop the app, then re-run it (Option A) or re-select the file via **Features → Location → Custom GPX…** (Option B).

### Timing

The Simulator paces playback using the `<time>` deltas between waypoints. Smaller time gaps = faster playback. There is no speed dial — control pace via the `velocity=` parameter when generating the file.

---

## Examples

```bash
# Minimal — auto-name from geocoding, 1s intervals, starts in 1 minute
simgpx BearLakeHike.kml

# Full control
simgpx BearLakeHike.kml \
  name="Bear Lake Hike" \
  start=now+5m \
  velocity=hike \
  output=./Desktop/BearLake

# Hiking pace from a file on the Desktop
simgpx ~/Desktop/MyTrip.kml velocity=hike

# Drive at 65 km/h, start at a specific time
simgpx route.kml start=2025-07-04T09:30 velocity=drive:65

# Spread the whole track over exactly 2 hours
simgpx route.kml velocity=total:2h

# Single GPS pin — no timing needed
simgpx 40.311200, -105.645900

# Named pin with custom output location
simgpx 40.311200, -105.645900 name="Bear Lake Trailhead" output=~/Desktop/BearLake
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `✗ KML file not found` | Check the path. Use `./` prefix for files in the current directory |
| Geocoding returns `unavailable` | No internet connection — supply `name=` and/or `output=` manually |
| Simulator doesn't move | Ensure the app calls `CLLocationManager.startUpdatingLocation()` and location permission is granted in the Simulator |
| Simulator shows Files app | Do not drag & drop — use Option A (Scheme) or Option B (Features menu) instead |
| Track plays too fast/slow | Adjust `velocity=` — use a preset (`walk`, `hike`, `drive`) or `total:` for exact duration |
| All points at same location | Your KML may be a Point, not a LineString — simgpx requires a LineString track |
