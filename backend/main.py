from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI
from fastapi import Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.model import SeverityModel
from backend.utils import (
    ACCIDENT_ZONES,
    HOTSPOT_RADIUS_METERS,
    build_ollama_client,
    fetch_nearby_places,
    fetch_nearby_context,
    fetch_osrm_routes,
    geocode_location,
    point_to_segment_distance_meters,
)


class RouteRequest(BaseModel):
    source: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)


app = FastAPI(title="Smart Driver Safety System", version="1.0.0")

# Keep local development simple when the frontend is opened separately.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

severity_model = SeverityModel(ollama_client=build_ollama_client())
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"


def transform_route_coordinates(osrm_coordinates: List[List[float]]) -> List[List[float]]:
    """Convert OSRM [lng, lat] pairs to Leaflet-friendly [lat, lng] pairs."""
    return [[lat, lng] for lng, lat in osrm_coordinates]


def classify_route_risk(route_score: int) -> str:
    # Simple thresholds tuned for the MVP scoring system.
    if route_score >= 5:
        return "RED"
    if route_score >= 3:
        return "ORANGE"
    return "BLUE"


def build_route_name(index: int, zones: List[Dict]) -> str:
    if not zones:
        return f"Route {index + 1} - Safer option"

    hotspot_names = ", ".join(zone["name"] for zone in zones[:2])
    return f"Route {index + 1} - via {hotspot_names}"


def classify_segment_color(zone_severity: str) -> str:
    if zone_severity == "HIGH":
        return "RED"
    if zone_severity == "MEDIUM":
        return "ORANGE"
    return "BLUE"


def build_route_segments(coordinates: List[List[float]], zone_hits: List[Dict]) -> List[Dict]:
    """Split the route into traffic-style colored segments."""
    if len(coordinates) < 2:
        return []

    segments = []
    for index in range(len(coordinates) - 1):
        start = coordinates[index]
        end = coordinates[index + 1]

        matching_zone = None
        for zone in zone_hits:
            segment_distance = point_to_segment_distance_meters(
                point_lat=zone["lat"],
                point_lng=zone["lng"],
                start_lat=start[0],
                start_lng=start[1],
                end_lat=end[0],
                end_lng=end[1],
            )
            if segment_distance <= HOTSPOT_RADIUS_METERS:
                matching_zone = zone
                break

        if matching_zone:
            color = classify_segment_color(matching_zone["severity"])
            severity = matching_zone["severity"]
            zone_name = matching_zone["name"]
        else:
            color = "BLUE"
            severity = "LOW"
            zone_name = None

        segments.append(
            {
                "coordinates": [start, end],
                "color": color,
                "severity": severity,
                "zone_name": zone_name,
            }
        )

    return segments


@app.post("/analyze-routes")
async def analyze_routes(payload: RouteRequest) -> Dict:
    # Step 1: Convert source and destination strings to coordinates.
    source_coords = geocode_location(payload.source)
    destination_coords = geocode_location(payload.destination)

    # Step 2 and 3: Fetch alternative routes from OSRM in GeoJSON form.
    osrm_routes = await fetch_osrm_routes(source_coords, destination_coords)
    response_routes = []

    for route in osrm_routes:
        geometry = route.get("geometry", {})
        raw_coordinates = geometry.get("coordinates", [])
        converted_coordinates = transform_route_coordinates(raw_coordinates)
        route_score = 0
        intersecting_zones = []
        seen_zone_names = set()

        # Step 6: Check each route segment against the hardcoded accident zones.
        for zone in ACCIDENT_ZONES:
            min_distance = None
            for index in range(len(converted_coordinates) - 1):
                start = converted_coordinates[index]
                end = converted_coordinates[index + 1]
                segment_distance = point_to_segment_distance_meters(
                    point_lat=zone["lat"],
                    point_lng=zone["lng"],
                    start_lat=start[0],
                    start_lng=start[1],
                    end_lat=end[0],
                    end_lng=end[1],
                )
                if min_distance is None or segment_distance < min_distance:
                    min_distance = segment_distance

            if min_distance is None or min_distance > HOTSPOT_RADIUS_METERS:
                continue

            if zone["name"] in seen_zone_names:
                continue

            prediction = await severity_model.predict(
                accidents=zone["accidents"],
                deaths=zone["deaths"],
                frequency=zone["frequency"],
                zone_name=zone["name"],
            )

            # Step 7: Increase route score using zone severity.
            if prediction.severity == "HIGH":
                route_score += 3
            elif prediction.severity == "MEDIUM":
                route_score += 2
            else:
                route_score += 1

            nearby_context = await fetch_nearby_context(zone["lat"], zone["lng"])

            intersecting_zones.append(
                {
                    "name": zone["name"],
                    "lat": zone["lat"],
                    "lng": zone["lng"],
                    "severity": prediction.severity,
                    "severity_score": prediction.score,
                    "distance_m": round(min_distance, 2),
                    "road_name": zone["road_name"],
                    **nearby_context,
                }
            )
            seen_zone_names.add(zone["name"])

        # Step 8: Convert the cumulative score into RED / ORANGE / BLUE.
        risk_level = classify_route_risk(route_score)
        route_segments = build_route_segments(converted_coordinates, intersecting_zones)

        response_routes.append(
            {
                "route_name": build_route_name(len(response_routes), intersecting_zones),
                "coordinates": converted_coordinates,
                "segments": route_segments,
                "risk_level": risk_level,
                "risk_score": route_score,
                "distance_m": round(route.get("distance", 0), 2),
                "duration_s": round(route.get("duration", 0), 2),
                "zones": intersecting_zones,
            }
        )

    return {"routes": response_routes}


@app.get("/")
async def serve_index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")


@app.get("/nearby-places")
async def nearby_places(
    lat: float = Query(...),
    lng: float = Query(...),
    type: str = Query(..., pattern="^(hospital|police|hotel|pharmacy)$"),
) -> Dict:
    places = await fetch_nearby_places(lat=lat, lng=lng, place_type=type)
    return {"places": places}
