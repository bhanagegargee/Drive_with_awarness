import json
import os
from math import asin, cos, radians, sin, sqrt
from typing import Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException

from backend.model import SeverityPrediction


ACCIDENT_ZONES: List[Dict] = [
    {
        "name": "Navale Bridge / Narhe Selfie Point",
        "lat": 18.4525,
        "lng": 73.8344,
        "accidents": 68,
        "deaths": 14,
        "frequency": 11,
        "road_name": "Pune-Bengaluru Highway",
    },
    {
        "name": "Katraj Chowk",
        "lat": 18.4530,
        "lng": 73.8631,
        "accidents": 46,
        "deaths": 9,
        "frequency": 8,
        "road_name": "Pune-Satara Road",
    },
]

LOCATION_MAP: Dict[str, Tuple[float, float]] = {
    "anand nagar": (18.4692, 73.8233),
    "hinjawadi": (18.5913, 73.7389),
    "wakad": (18.5995, 73.7637),
    "baner": (18.5590, 73.7868),
    "shivajinagar": (18.5308, 73.8475),
    "kothrud": (18.5074, 73.8077),
    "pune station": (18.5286, 73.8743),
    "magarpatta": (18.5154, 73.9318),
    "hadapsar": (18.5089, 73.9260),
    "swargate": (18.5012, 73.8636),
    "katraj": (18.4530, 73.8631),
    "sinhgad road": (18.4570, 73.8445),
}

OSRM_BASE_URL = "https://router.project-osrm.org"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()
HOTSPOT_RADIUS_METERS = 500


def normalize_place_name(place: str) -> str:
    return place.strip().lower()


def geocode_location(place: str) -> Tuple[float, float]:
    """Resolve a place from a predefined MVP mapping or a raw 'lat,lng' string."""
    normalized = normalize_place_name(place)

    if normalized in LOCATION_MAP:
        return LOCATION_MAP[normalized]

    if "," in place:
        try:
            lat_str, lng_str = [part.strip() for part in place.split(",", 1)]
            lat = float(lat_str)
            lng = float(lng_str)
            return lat, lng
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid coordinate format: {place}") from exc

    supported_places = ", ".join(sorted(LOCATION_MAP.keys()))
    raise HTTPException(
        status_code=400,
        detail=(
            f"Unknown location '{place}'. Use one of the predefined MVP locations "
            f"({supported_places}) or pass coordinates as 'lat,lng'."
        ),
    )


def haversine_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in meters between two latitude/longitude pairs."""
    earth_radius_m = 6371000

    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    start_lat = radians(lat1)
    end_lat = radians(lat2)

    a = sin(d_lat / 2) ** 2 + cos(start_lat) * cos(end_lat) * sin(d_lng / 2) ** 2
    c = 2 * asin(sqrt(a))
    return earth_radius_m * c


def point_to_segment_distance_meters(
    point_lat: float,
    point_lng: float,
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> float:
    """
    Approximate the shortest distance from a hotspot point to a route segment in meters.
    Uses a local planar projection, which is accurate enough at city scale.
    """
    reference_lat_rad = radians((start_lat + end_lat + point_lat) / 3)
    meters_per_lat = 111320
    meters_per_lng = 111320 * cos(reference_lat_rad)

    point_x = point_lng * meters_per_lng
    point_y = point_lat * meters_per_lat
    start_x = start_lng * meters_per_lng
    start_y = start_lat * meters_per_lat
    end_x = end_lng * meters_per_lng
    end_y = end_lat * meters_per_lat

    dx = end_x - start_x
    dy = end_y - start_y

    if dx == 0 and dy == 0:
        return sqrt((point_x - start_x) ** 2 + (point_y - start_y) ** 2)

    projection = ((point_x - start_x) * dx + (point_y - start_y) * dy) / ((dx * dx) + (dy * dy))
    projection = max(0, min(1, projection))

    closest_x = start_x + projection * dx
    closest_y = start_y + projection * dy
    return sqrt((point_x - closest_x) ** 2 + (point_y - closest_y) ** 2)


class OllamaSeverityClient:
    """Optional local Ollama integration for severity enrichment."""

    def __init__(self, model_name: str, endpoint: str = OLLAMA_URL) -> None:
        self.model_name = model_name
        self.endpoint = endpoint

    async def predict(
        self, accidents: int, deaths: int, frequency: int, zone_name: str
    ) -> Optional[SeverityPrediction]:
        prompt = f"""
You are helping a smart driver safety system estimate hotspot severity.
Return strict JSON only in this shape:
{{"score": number, "severity": "HIGH" | "MEDIUM" | "LOW"}}

Hotspot: {zone_name}
Historical data:
- accidents: {accidents}
- deaths: {deaths}
- frequency: {frequency}

Rules:
- Produce a score between 0 and 100.
- Use HIGH when score > 70, MEDIUM when score > 40, else LOW.
"""

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    self.endpoint,
                    json={
                        "model": self.model_name,
                        "prompt": prompt.strip(),
                        "stream": False,
                        "format": "json",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            return None

        raw_response = payload.get("response", "").strip()
        if not raw_response:
            return None

        try:
            parsed = json.loads(raw_response)
            score = float(parsed["score"])
            severity = str(parsed["severity"]).upper()
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

        if severity not in {"HIGH", "MEDIUM", "LOW"}:
            return None

        return SeverityPrediction(score=round(max(0, min(100, score)), 2), severity=severity)


def build_ollama_client() -> Optional[OllamaSeverityClient]:
    if not OLLAMA_MODEL:
        return None
    return OllamaSeverityClient(model_name=OLLAMA_MODEL)


async def fetch_osrm_routes(source: Tuple[float, float], destination: Tuple[float, float]) -> List[Dict]:
    """Fetch alternative routes from the public OSRM API in GeoJSON format."""
    src_lat, src_lng = source
    dst_lat, dst_lng = destination
    coordinates = f"{src_lng},{src_lat};{dst_lng},{dst_lat}"
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/{coordinates}"
        "?alternatives=true&geometries=geojson&overview=full&steps=false"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to fetch routes from OSRM.") from exc

    payload = response.json()
    routes = payload.get("routes", [])
    if not routes:
        raise HTTPException(status_code=404, detail="No routes returned by OSRM.")

    return routes


async def fetch_nearby_context(zone_lat: float, zone_lng: float) -> Dict:
    """
    Fetch a small amount of nearby road context from Overpass.
    This is optional enrichment, so failures return an empty payload.
    """
    query = f"""
    [out:json][timeout:15];
    (
      way(around:350,{zone_lat},{zone_lng})["highway"];
      node(around:350,{zone_lat},{zone_lng})["amenity"];
    );
    out center 10;
    """

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(OVERPASS_URL, content=query)
            response.raise_for_status()
            data = response.json()
    except Exception:
        return {}

    elements = data.get("elements", [])
    highway_names = []
    amenities = []

    for element in elements:
        tags = element.get("tags", {})
        if "highway" in tags and tags.get("name"):
            highway_names.append(tags["name"])
        if "amenity" in tags:
            amenities.append(tags["amenity"])

    return {
        "nearby_roads": sorted(set(highway_names))[:3],
        "nearby_amenities": sorted(set(amenities))[:3],
    }


async def fetch_nearby_places(lat: float, lng: float, place_type: str) -> List[Dict]:
    """Fetch nearby essential amenities from Overpass based on the requested type."""
    place_filters = {
        "hospital": 'node(around:3000,{lat},{lng})["amenity"="hospital"];',
        "police": 'node(around:3000,{lat},{lng})["amenity"="police"];',
        "hotel": 'node(around:3000,{lat},{lng})["tourism"="hotel"];',
        "pharmacy": 'node(around:3000,{lat},{lng})["amenity"="pharmacy"];',
    }

    if place_type not in place_filters:
        raise HTTPException(status_code=400, detail="Unsupported place type.")

    query = f"""
    [out:json][timeout:20];
    (
      {place_filters[place_type].format(lat=lat, lng=lng)}
    );
    out center 25;
    """

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(OVERPASS_URL, content=query)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Unable to fetch nearby places from Overpass.") from exc

    places = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        place_name = tags.get("name", "Unnamed Place")
        place_lat = element.get("lat") or element.get("center", {}).get("lat")
        place_lng = element.get("lon") or element.get("center", {}).get("lon")

        if place_lat is None or place_lng is None:
            continue

        places.append(
            {
                "name": place_name,
                "lat": place_lat,
                "lng": place_lng,
                "type": place_type,
            }
        )

    return places
