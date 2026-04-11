$outputPath = "C:\Users\HomePC\Documents\New project\Smart_Driver_Safety_System_Presentation.pptx"

$powerPoint = New-Object -ComObject PowerPoint.Application
$powerPoint.Visible = [Microsoft.Office.Core.MsoTriState]::msoTrue
$presentation = $powerPoint.Presentations.Add()

function Add-BulletSlide {
    param(
        [string]$Title,
        [string[]]$Bullets
    )

    $slide = $presentation.Slides.Add($presentation.Slides.Count + 1, 2)
    $slide.Shapes.Title.TextFrame.TextRange.Text = $Title

    $body = $slide.Shapes.Item(2).TextFrame.TextRange
    $body.Text = ($Bullets -join "`r`n")
}

Add-BulletSlide -Title "Smart Driver Safety System" -Bullets @(
    "MVP web application for safer route selection and nearby help services",
    "Shows accident-prone route segments on map",
    "Lets driver find hospitals, police stations, hotels, and pharmacies nearby",
    "Built with simple, practical full-stack technologies"
)

Add-BulletSlide -Title "Problem Statement" -Bullets @(
    "Drivers usually choose the fastest route, not the safest route",
    "Accident-prone areas are not clearly shown during route selection",
    "In emergencies, drivers need quick access to nearby essential amenities",
    "Users need one system for route safety and emergency support"
)

Add-BulletSlide -Title "Main Problems Found During Build" -Bullets @(
    "Route hotspot detection was missing some dangerous areas",
    "Destination coordinates and hotspot coordinates were not always aligned",
    "Amenity search depended on browser location permission and could time out",
    "Users needed clearer route choices and ranked nearby place results"
)

Add-BulletSlide -Title "Solutions We Implemented" -Bullets @(
    "Used route segment distance instead of only route points for hotspot detection",
    "Aligned important locations like Katraj with real hotspot coordinates",
    "Added clear error handling for geolocation timeout and permission denial",
    "Listed all available routes and ranked amenities by user distance"
)

Add-BulletSlide -Title "Proposed System Flow" -Bullets @(
    "User selects source and destination",
    "Backend fetches multiple routes from OSRM",
    "System checks routes against accident hotspots",
    "Frontend shows safer and riskier route segments in different colors",
    "User can also open menu and find nearby essential amenities"
)

Add-BulletSlide -Title "Route Safety Logic" -Bullets @(
    "Two accident hotspots are stored with latitude and longitude",
    "Each route is split into segments",
    "Each segment is checked against hotspot radius",
    "Dangerous segments are shown in red or orange, safer segments in blue",
    "Overall route risk score is calculated from hotspot severity"
)

Add-BulletSlide -Title "Nearby Amenities Feature" -Bullets @(
    "Hamburger menu opens a sidebar on the map",
    "User selects Hospitals, Police Stations, Hotels, or Medical Stores",
    "System gets current location from browser geolocation",
    "Backend fetches nearby places from Overpass API",
    "Results appear on the map and in a ranked list below the map"
)

Add-BulletSlide -Title "Problems and Fixes for Amenities" -Bullets @(
    "Location timeout error happened when browser could not get user position in time",
    "Permission denied error happened when location access was blocked",
    "We added user-friendly messages for both cases",
    "We clear old markers before loading a new amenity category",
    "We allow routing from user location to selected amenity"
)

Add-BulletSlide -Title "Tech Stack Used" -Bullets @(
    "Frontend: HTML, CSS, JavaScript",
    "Map Library: Leaflet.js with OpenStreetMap tiles",
    "Backend: Python FastAPI",
    "Routing API: OSRM public API",
    "Nearby Places API: Overpass API",
    "ML Logic: Rule-based severity model with optional Ollama enrichment"
)

Add-BulletSlide -Title "Why This Tech Stack" -Bullets @(
    "FastAPI is simple, fast, and good for API building",
    "Leaflet is lightweight and easy for interactive maps",
    "OSRM gives multiple route options with geometry data",
    "Overpass helps fetch real nearby OpenStreetMap places",
    "Rule-based ML is easy to explain in an MVP"
)

Add-BulletSlide -Title "APIs Used Smoothly" -Bullets @(
    "Frontend talks only to our FastAPI backend",
    "Backend handles external API calls and response formatting",
    "This keeps the frontend clean and modular",
    "Errors are caught and shown clearly to user",
    "Existing route logic was reused for routing to amenities"
)

Add-BulletSlide -Title "Project Outcome" -Bullets @(
    "User can compare multiple routes before travelling",
    "Dangerous road sections are highlighted clearly",
    "Nearby essential amenities can be found quickly",
    "Selected amenity can be used as destination for safe routing",
    "Project is modular and ready for future scaling"
)

Add-BulletSlide -Title "Future Improvements" -Bullets @(
    "Use real accident datasets from traffic or police sources",
    "Store hotspots and locations in a database",
    "Add live traffic and weather data",
    "Add hospital details like emergency availability",
    "Add user login, trip history, and analytics dashboard"
)

$presentation.SaveAs($outputPath)
$presentation.Close()
$powerPoint.Quit()

[System.Runtime.Interopservices.Marshal]::ReleaseComObject($presentation) | Out-Null
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($powerPoint) | Out-Null
[GC]::Collect()
[GC]::WaitForPendingFinalizers()

Write-Output $outputPath
