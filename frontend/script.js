const map = L.map("map").setView([18.5204, 73.8567], 12);

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const form = document.getElementById("route-form");
const sourceInput = document.getElementById("source");
const destinationInput = document.getElementById("destination");
const statusBox = document.getElementById("status");
const routeList = document.getElementById("route-list");
const submitButton = document.getElementById("submit-btn");
const menuToggle = document.getElementById("menu-toggle");
const sidebar = document.getElementById("sidebar");
const sidebarClose = document.getElementById("sidebar-close");
const sidebarItems = document.querySelectorAll(".sidebar-item");
const amenityList = document.getElementById("amenity-list");
const amenitySummary = document.getElementById("amenity-summary");

const routeLayers = [];
let selectedRouteIndex = null;
let zoneLayerGroup = L.layerGroup().addTo(map);
let amenityLayerGroup = L.layerGroup().addTo(map);
let userMarker = null;
let watchId = null;
let currentAmenityPlaces = [];

const DEFAULT_LOCATION = {
    lat: 18.5204,
    lng: 73.8567,
};

const GEOLOCATION_OPTIONS = {
    enableHighAccuracy: true,
    timeout: 15000,
    maximumAge: 0,
};

const riskColors = {
    RED: "#c9443d",
    ORANGE: "#d98620",
    BLUE: "#1d78c1",
};

let userLocation = null;
let locationFetchInProgress = false;
let locationWatchStarted = false;
let fallbackAlertShown = false;
const pendingLocationCallbacks = [];

function setStatus(message, isError = false) {
    statusBox.textContent = message;
    statusBox.style.color = isError ? "#b1372e" : "#627077";
}

function clearMapRoutes() {
    routeLayers.forEach((routeGroup) => {
        routeGroup.segments.forEach((segment) => map.removeLayer(segment.layer));
    });
    routeLayers.length = 0;
    zoneLayerGroup.clearLayers();
    routeList.innerHTML = "";
    selectedRouteIndex = null;
}

function clearAmenityMarkers() {
    amenityLayerGroup.clearLayers();
}

function clearAmenityList(message = "Choose a category from the menu to view nearby places.") {
    currentAmenityPlaces = [];
    amenitySummary.textContent = message;
    amenityList.innerHTML = "";
}

function formatDistance(distanceM) {
    return `${(distanceM / 1000).toFixed(1)} km`;
}

function formatDuration(durationS) {
    const minutes = Math.round(durationS / 60);
    if (minutes < 60) {
        return `${minutes} min`;
    }

    const hours = Math.floor(minutes / 60);
    const remaining = minutes % 60;
    return `${hours} hr ${remaining} min`;
}

function drawZones(zones) {
    zoneLayerGroup.clearLayers();

    zones.forEach((zone) => {
        const marker = L.circleMarker([zone.lat, zone.lng], {
            radius: 10,
            color: "#7a2d91",
            fillColor: "#7a2d91",
            fillOpacity: 0.85,
            weight: 2,
        });

        const roads = (zone.nearby_roads || []).join(", ") || "Not available";
        const amenities = (zone.nearby_amenities || []).join(", ") || "Not available";

        marker.bindPopup(`
            <strong>${zone.name}</strong><br>
            Corridor: ${zone.road_name}<br>
            Severity: ${zone.severity}<br>
            Score: ${zone.severity_score}<br>
            Nearby roads: ${roads}<br>
            Nearby amenities: ${amenities}
        `);
        marker.addTo(zoneLayerGroup);
    });
}

function openSidebar() {
    sidebar.classList.add("open");
}

function closeSidebar() {
    sidebar.classList.remove("open");
}

function getFallbackLocation() {
    return {
        lat: DEFAULT_LOCATION.lat,
        lng: DEFAULT_LOCATION.lng,
        source: "fallback",
    };
}

function flushLocationCallbacks(location) {
    while (pendingLocationCallbacks.length) {
        const callback = pendingLocationCallbacks.shift();
        callback(location);
    }
}

function updateUserMarker(location) {
    const latLng = [location.lat, location.lng];

    if (!userMarker) {
        userMarker = L.circleMarker(latLng, {
            radius: 9,
            color: "#ffffff",
            weight: 3,
            fillColor: "#1aaf5d",
            fillOpacity: 1,
        }).addTo(map);
        userMarker.bindPopup("Driver live location");
    } else {
        userMarker.setLatLng(latLng);
    }
}

function resolveLocationSuccess(position) {
    userLocation = {
        lat: position.coords.latitude,
        lng: position.coords.longitude,
        source: "device",
    };
    locationFetchInProgress = false;
    updateUserMarker(userLocation);
    flushLocationCallbacks(userLocation);
}

function resolveLocationFailure(error) {
    console.error("Geolocation error:", error);

    if (error && error.code === 1) {
        setStatus("Location permission denied. Please enable it.", true);
        alert("Location permission denied. Please enable it.");
    } else {
        if (!fallbackAlertShown) {
            alert("Unable to fetch your location. Using default location.");
            fallbackAlertShown = true;
        }
        setStatus("Unable to fetch your location. Using default location.", true);
    }

    userLocation = getFallbackLocation();
    locationFetchInProgress = false;
    updateUserMarker(userLocation);
    flushLocationCallbacks(userLocation);
}

function requestLocation(attempt = 0) {
    if (!("geolocation" in navigator)) {
        resolveLocationFailure(new Error("Geolocation is not supported by this browser."));
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => resolveLocationSuccess(position),
        (error) => {
            console.error(`Geolocation attempt ${attempt + 1} failed:`, error);

            // Geolocation requires HTTPS or localhost in modern browsers.
            if (attempt === 0 && error.code !== 1) {
                requestLocation(1);
                return;
            }

            resolveLocationFailure(error);
        },
        GEOLOCATION_OPTIONS
    );
}

function getUserLocation(callback) {
    if (userLocation) {
        callback(userLocation);
        return;
    }

    pendingLocationCallbacks.push(callback);

    if (locationFetchInProgress) {
        return;
    }

    locationFetchInProgress = true;
    setStatus("Fetching location...");
    requestLocation();
}

function getUserLocationAsync() {
    return new Promise((resolve) => {
        getUserLocation(resolve);
    });
}

async function fetchNearbyPlaces(lat, lng, type) {
    const response = await fetch(`/nearby-places?lat=${lat}&lng=${lng}&type=${type}`);
    const payload = await response.json();

    if (!response.ok) {
        throw new Error(payload.detail || "Unable to fetch nearby places.");
    }

    return payload.places || [];
}

async function routeToPlace(place) {
    try {
        setStatus(`Finding safe routes to ${place.name}...`);

        // Replaced old direct getCurrentPosition() usage with cached central handler.
        const location = await getUserLocationAsync();

        clearMapRoutes();
        const payload = await analyzeRoutes(`${location.lat},${location.lng}`, `${place.lat},${place.lng}`);
        const routes = payload.routes || [];

        if (!routes.length) {
            setStatus(`No routes found to ${place.name}.`, true);
            return;
        }

        renderRouteList(routes);
        drawRoutes(routes);
        drawAmenityMarkers([place], true);
        highlightAmenityCard(place);
        setStatus(`Loaded ${routes.length} route option(s) to ${place.name}.`);
    } catch (error) {
        setStatus(`Unable to route to selected place: ${error.message}`, true);
    }
}

function drawAmenityMarkers(places, focusBounds = true) {
    clearAmenityMarkers();
    const bounds = [];

    places.forEach((place) => {
        const marker = L.marker([place.lat, place.lng]).addTo(amenityLayerGroup);
        marker.bindPopup(`<strong>${place.name}</strong><br>Type: ${place.type}`);
        marker.on("click", () => {
            highlightAmenityCard(place);
            routeToPlace(place);
        });
        bounds.push([place.lat, place.lng]);
    });

    if (focusBounds && bounds.length) {
        map.fitBounds(bounds, { padding: [40, 40] });
    }
}

function formatAmenityDistance(distanceMeters) {
    if (distanceMeters < 1000) {
        return `${Math.round(distanceMeters)} m away`;
    }
    return `${(distanceMeters / 1000).toFixed(2)} km away`;
}

function haversineDistance(lat1, lng1, lat2, lng2) {
    const toRadians = (value) => (value * Math.PI) / 180;
    const earthRadius = 6371000;
    const dLat = toRadians(lat2 - lat1);
    const dLng = toRadians(lng2 - lng1);
    const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.sin(dLng / 2) ** 2;
    return 2 * earthRadius * Math.asin(Math.sqrt(a));
}

function highlightAmenityCard(place) {
    [...amenityList.children].forEach((card) => {
        card.classList.toggle("active", card.dataset.placeName === place.name && card.dataset.placeType === place.type);
    });
}

function renderAmenityList(places, type) {
    currentAmenityPlaces = places;
    amenityList.innerHTML = "";

    if (!places.length) {
        amenitySummary.textContent = `No nearby ${type}s found around your location.`;
        return;
    }

    amenitySummary.textContent = `${places.length} nearby ${type}(s), ranked by distance from your location.`;

    places.forEach((place, index) => {
        const card = document.createElement("article");
        card.className = "amenity-card";
        card.dataset.placeName = place.name;
        card.dataset.placeType = place.type;
        card.innerHTML = `
            <div class="amenity-card-head">
                <strong>${place.name}</strong>
                <span class="amenity-rank">#${index + 1}</span>
            </div>
            <div class="amenity-meta">
                Type: ${place.type} | ${formatAmenityDistance(place.distance_m)}
            </div>
            <button type="button" class="amenity-action">Route Here</button>
        `;

        card.addEventListener("click", () => {
            highlightAmenityCard(place);
            routeToPlace(place);
        });
        card.querySelector(".amenity-action").addEventListener("click", (event) => {
            event.stopPropagation();
            highlightAmenityCard(place);
            routeToPlace(place);
        });
        amenityList.appendChild(card);
    });
}

async function handleAmenitySelection(type) {
    closeSidebar();
    clearAmenityMarkers();
    setStatus(`Fetching nearby ${type}s...`);

    try {
        // Replaced old direct getCurrentPosition() usage with cached central handler.
        const location = await getUserLocationAsync();

        const places = await fetchNearbyPlaces(location.lat, location.lng, type);
        const rankedPlaces = places
            .map((place) => ({
                ...place,
                distance_m: haversineDistance(location.lat, location.lng, place.lat, place.lng),
            }))
            .sort((first, second) => first.distance_m - second.distance_m);

        if (!rankedPlaces.length) {
            clearAmenityList(`No nearby ${type}s found around your location.`);
            setStatus(`No nearby ${type}s found around your location.`, true);
            return;
        }

        renderAmenityList(rankedPlaces, type);
        drawAmenityMarkers(rankedPlaces);
        setStatus(`Loaded ${rankedPlaces.length} nearby ${type}(s). Click a marker or choose one from the list.`);
    } catch (error) {
        clearAmenityList("Unable to load nearby amenities right now.");
        setStatus(`Unable to fetch nearby places: ${error.message}`, true);
    }
}

function selectRoute(index, routes) {
    selectedRouteIndex = index;

    routeLayers.forEach((routeGroup, routeIndex) => {
        const isSelected = routeIndex === index;
        routeGroup.segments.forEach((segment) => {
            segment.layer.setStyle({
                color: segment.color,
                weight: isSelected ? 8 : 5,
                opacity: isSelected ? 1 : 0.45,
            });
        });
    });

    [...routeList.children].forEach((card, cardIndex) => {
        card.classList.toggle("selected", cardIndex === index);
    });

    const selectedRoute = routes[index];
    drawZones(selectedRoute.zones);

    const latLngs = selectedRoute.coordinates.map(([lat, lng]) => L.latLng(lat, lng));
    map.fitBounds(L.latLngBounds(latLngs), { padding: [30, 30] });
}

function renderRouteList(routes) {
    routeList.innerHTML = "";

    routes.forEach((route, index) => {
        const card = document.createElement("article");
        card.className = "route-card";

        const zoneMarkup = route.zones.length
            ? route.zones.map((zone) => `<span class="zone-chip">${zone.name}: ${zone.severity}</span>`).join("")
            : `<span class="zone-chip">No hotspot intersection</span>`;

        card.innerHTML = `
            <div class="route-header">
                <strong>${route.route_name || `Route ${index + 1}`}</strong>
                <span class="badge ${route.risk_level.toLowerCase()}">${route.risk_level}</span>
            </div>
            <div class="route-meta">
                Risk score: ${route.risk_score} | Distance: ${formatDistance(route.distance_m)} | Duration: ${formatDuration(route.duration_s)}
            </div>
            <div>${zoneMarkup}</div>
            <button type="button" class="route-select-btn">Select Route</button>
        `;

        card.addEventListener("click", () => selectRoute(index, routes));
        card.querySelector(".route-select-btn").addEventListener("click", (event) => {
            event.stopPropagation();
            selectRoute(index, routes);
        });
        routeList.appendChild(card);
    });
}

function drawRoutes(routes) {
    const bounds = [];

    routes.forEach((route, index) => {
        const segments = (route.segments || []).map((segment) => {
            const color = riskColors[segment.color] || riskColors.BLUE;
            const layer = L.polyline(segment.coordinates, {
                color,
                weight: 5,
                opacity: 0.45,
                lineCap: "round",
            }).addTo(map);

            if (segment.zone_name) {
                layer.bindPopup(
                    `Route ${index + 1}<br>Hotspot: ${segment.zone_name}<br>Segment severity: ${segment.severity}`
                );
            } else {
                layer.bindPopup(`Route ${index + 1}<br>Normal segment`);
            }

            layer.on("click", () => selectRoute(index, routes));
            return { layer, color };
        });

        routeLayers.push({ segments });
        bounds.push(...route.coordinates);
    });

    if (bounds.length > 0) {
        map.fitBounds(bounds, { padding: [30, 30] });
    }

    selectRoute(0, routes);
}

async function analyzeRoutes(source, destination) {
    const response = await fetch("/analyze-routes", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ source, destination }),
    });

    const payload = await response.json();
    if (!response.ok) {
        throw new Error(payload.detail || "Unable to analyze routes.");
    }

    return payload;
}

function startLiveTracking() {
    if (locationWatchStarted || !("geolocation" in navigator)) {
        if (!("geolocation" in navigator)) {
            setStatus("Geolocation is not supported by this browser.");
        }
        return;
    }

    locationWatchStarted = true;

    if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
    }

    watchId = navigator.geolocation.watchPosition(
        (position) => {
            userLocation = {
                lat: position.coords.latitude,
                lng: position.coords.longitude,
                source: "device",
            };
            updateUserMarker(userLocation);
        },
        (error) => {
            console.error("Location tracking error:", error);
        },
        GEOLOCATION_OPTIONS
    );
}

function initializeLocation() {
    // Geolocation works only on HTTPS or localhost in modern browsers.
    getUserLocation((location) => {
        updateUserMarker(location);
        startLiveTracking();

        if (location.source === "fallback") {
            map.setView([location.lat, location.lng], 12);
            return;
        }

        map.setView([location.lat, location.lng], 13);
        setStatus("Location ready.");
    });
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const source = sourceInput.value.trim();
    const destination = destinationInput.value.trim();

    if (!source || !destination) {
        setStatus("Please enter both source and destination.", true);
        return;
    }

    clearMapRoutes();
    clearAmenityMarkers();
    submitButton.disabled = true;
    setStatus("Analyzing all possible routes and highlighting hotspot segments...");

    try {
        const payload = await analyzeRoutes(source, destination);
        const routes = payload.routes || [];

        if (!routes.length) {
            setStatus("No routes were returned for this trip.", true);
            return;
        }

        renderRouteList(routes);
        drawRoutes(routes);
        setStatus(`Loaded ${routes.length} route option(s). All routes are visible; click one to inspect hotspot details.`);
    } catch (error) {
        setStatus(error.message, true);
    } finally {
        submitButton.disabled = false;
    }
});

menuToggle.addEventListener("click", openSidebar);
sidebarClose.addEventListener("click", closeSidebar);
sidebarItems.forEach((item) => {
    item.addEventListener("click", () => handleAmenitySelection(item.dataset.type));
});

clearAmenityList();
initializeLocation();
