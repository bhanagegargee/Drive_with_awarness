# Smart Driver Safety System

A full-stack MVP web application that helps drivers choose safer routes and quickly find nearby essential amenities.

The system analyzes multiple routes between a source and destination, detects accident-prone segments, assigns risk levels, and visualizes safer and riskier paths on an interactive map. It also helps users discover nearby hospitals, police stations, hotels, and pharmacies, then safely route to a selected place.

## Features

- Multiple route analysis using OSRM
- Accident hotspot detection on route segments
- Risk classification with `RED`, `ORANGE`, and `BLUE` route overlays
- Real-time driver location tracking with browser geolocation
- Nearby amenities sidebar with:
  - Hospitals
  - Police Stations
  - Hotels
  - Medical Stores
- Ranked amenity results by distance from the user
- Route-to-selected-amenity using the same existing safety logic
- Fallback geolocation handling to avoid timeout failures

## Tech Stack

### Frontend

- HTML
- CSS
- Vanilla JavaScript
- Leaflet.js
- OpenStreetMap tiles

### Backend

- Python
- FastAPI
- httpx

### External APIs

- OSRM public API for routing
- Overpass API for nearby OpenStreetMap data

### Risk Logic

- Rule-based severity model
- Optional Ollama-based enrichment

## Project Structure

```text
backend/
  main.py
  model.py
  utils.py

frontend/
  index.html
  style.css
  script.js

requirements.txt
README.md
```

## How It Works

### 1. Route Safety Flow

1. User selects source and destination.
2. Frontend sends request to `POST /analyze-routes`.
3. Backend resolves place names to coordinates.
4. Backend fetches alternative routes from OSRM.
5. Route segments are checked against accident hotspots.
6. Hotspots are scored using the severity model.
7. Backend returns route geometry, segments, hotspot details, and route risk.
8. Frontend draws all available routes on the map.
9. Dangerous segments are highlighted:
   - `RED` for high risk
   - `ORANGE` for medium risk
   - `BLUE` for lower risk

### 2. Nearby Amenities Flow

1. User opens the hamburger menu.
2. User selects a category such as Hospitals or Police Stations.
3. Frontend gets the user location using the centralized geolocation handler.
4. Frontend calls `GET /nearby-places`.
5. Backend queries Overpass API and returns nearby places.
6. Frontend:
   - places markers on the map
   - lists places below the map
   - ranks them by distance from the user
7. When the user clicks a marker or list item, the app routes safely to that selected place.

## Accident Hotspots Used

The MVP currently uses two important accident-prone hotspots in Pune:

- `Navale Bridge / Narhe Selfie Point`
- `Katraj Chowk`

These hotspots are used to detect whether a route passes close to a dangerous road section.

## Supported Locations

The location dropdown currently supports:

- Anand Nagar
- Baner
- Hadapsar
- Hinjawadi
- Katraj
- Kothrud
- Magarpatta
- Pune Station
- Shivajinagar
- Sinhgad Road
- Swargate
- Wakad

## Geolocation Handling

The frontend includes a robust location handler to prevent repeated geolocation timeout issues.

### What it does

- fetches location once at app startup
- caches the result globally
- reuses the cached location across features
- retries once if location fetch fails
- falls back to default Pune coordinates if location still fails

### Geolocation options used

```js
{
  enableHighAccuracy: true,
  timeout: 15000,
  maximumAge: 0
}
```

### Fallback location

If geolocation fails, the app uses:

- Latitude: `18.5204`
- Longitude: `73.8567`

### Important note

Browser geolocation works only on:

- `localhost`
- `HTTPS`

If the app is opened in an insecure context, location access may fail.

## Backend API Endpoints

### `POST /analyze-routes`

Analyzes route options and returns route safety information.

#### Request body

```json
{
  "source": "Swargate",
  "destination": "Katraj"
}
```

#### Response shape

```json
{
  "routes": [
    {
      "route_name": "Route 1 - via Katraj Chowk",
      "coordinates": [[18.5, 73.8]],
      "segments": [
        {
          "coordinates": [[18.5, 73.8], [18.6, 73.9]],
          "color": "RED",
          "severity": "HIGH",
          "zone_name": "Katraj Chowk"
        }
      ],
      "risk_level": "RED",
      "risk_score": 3,
      "distance_m": 12000,
      "duration_s": 1800,
      "zones": []
    }
  ]
}
```

### `GET /nearby-places`

Returns nearby amenities for the user location.

#### Query params

- `lat`
- `lng`
- `type` = `hospital | police | hotel | pharmacy`

#### Example

```text
/nearby-places?lat=18.5204&lng=73.8567&type=hospital
```

## Installation and Run

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2. Create virtual environment

```bash
python -m venv .venv
```

### 3. Activate virtual environment

#### Windows PowerShell

```powershell
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Optional Ollama setup

If you want to use Ollama for severity enrichment:

```powershell
$env:OLLAMA_MODEL="llama3.1"
```

Optional custom endpoint:

```powershell
$env:OLLAMA_URL="http://localhost:11434/api/generate"
```

If `OLLAMA_MODEL` is not set, the app uses the built-in rule-based severity model.

### 6. Run the FastAPI server

```bash
uvicorn backend.main:app --reload
```

### 7. Open in browser

```text
http://127.0.0.1:8000
```

## Common Issues

### 1. Geolocation timeout

Possible reasons:

- location services are disabled
- browser permission is blocked
- app is not running on `localhost` or `HTTPS`

Solution:

- enable browser location access
- use `localhost`
- allow GPS/location on device

If location still fails, the app automatically uses the fallback Pune location.

### 2. Nearby places not loading

Possible reasons:

- Overpass API is slow or temporarily unavailable
- internet connection issue

### 3. Routes not loading

Possible reasons:

- OSRM public API issue
- network problem
- source/destination not supported

## Why This Project Is Useful

- improves route awareness beyond just shortest path
- helps users identify risky road sections
- supports emergency decision-making with nearby amenities
- demonstrates full-stack integration of maps, APIs, geolocation, and route safety logic

## Future Improvements

- use real accident datasets from official traffic sources
- store hotspots in a database
- add live traffic integration
- add hospital emergency availability
- add driver alerts and voice guidance
- support authentication and trip history

## License

This project is currently for educational and MVP demonstration purposes.
