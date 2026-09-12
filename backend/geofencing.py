"""
Geofencing utilities for Umuve.

Defines the service area — the Atlantic coast from Miami-Dade up through
Broward, Palm Beach, Martin, St. Lucie, Indian River and Brevard (Cocoa
Beach / Titusville) — and provides functions to check whether coordinates
fall within it.
"""

from math import radians, cos, sin, asin, sqrt

# ---------------------------------------------------------------------------
# Service area definition -- seven coastal counties, Homestead to Titusville
# ---------------------------------------------------------------------------

# Quick bounding box for fast rejection before the more expensive polygon check.
SERVICE_AREA_BOUNDS = {
    "north": 28.80,   # Brevard / Volusia line (north of Titusville)
    "south": 25.30,   # southern Miami-Dade (Homestead / Florida City)
    "east": -79.85,   # Atlantic coastline
    "west": -81.00,   # western Brevard / Everglades boundary (stays east of Orlando)
}

# Center of the service area (geocoder proximity + default map center).
# Biased to the home market rather than the geometric middle.
SERVICE_AREA_CENTER = {
    "lat": 26.65,
    "lng": -80.20,
}

# Simplified polygon tracing the approximate boundary of the seven-county
# service area.  The polygon follows the coastline on the east and the
# county / Everglades borders on the west.  Vertices are listed
# counter-clockwise, south to north up the coast, then back down the west.
#
# Format: list of (lat, lng) tuples.
SERVICE_AREA_POLYGON = [
    (25.30, -80.40),   # 0  -- SW corner: south of Homestead
    (25.30, -80.15),   # 1  -- SE corner: south Miami-Dade coast
    (25.50, -80.10),   # 2  -- Biscayne Bay / Key Biscayne
    (25.80, -80.12),   # 3  -- Miami Beach area
    (26.05, -80.08),   # 4  -- Fort Lauderdale coast
    (26.35, -80.06),   # 5  -- Pompano / Deerfield Beach coast
    (26.55, -80.03),   # 6  -- Boca Raton coast
    (26.72, -80.03),   # 7  -- Boynton / Lake Worth coast
    (26.90, -80.04),   # 8  -- West Palm Beach coast
    (27.00, -80.08),   # 9  -- Jupiter / Tequesta coast
    (27.20, -80.15),   # 10 -- Stuart / Hutchinson Island
    (27.45, -80.25),   # 11 -- Fort Pierce coast
    (27.65, -80.32),   # 12 -- Vero Beach coast
    (27.86, -80.42),   # 13 -- Sebastian Inlet
    (28.10, -80.52),   # 14 -- Melbourne / Satellite Beach
    (28.45, -80.50),   # 15 -- Cocoa Beach / Cape Canaveral
    (28.62, -80.58),   # 16 -- Titusville / Merritt Island coast
    (28.80, -80.75),   # 17 -- NE corner: Brevard / Volusia line
    (28.80, -81.00),   # 18 -- NW corner: western Brevard (St. Johns marsh)
    (28.30, -81.00),   # 19 -- western Brevard / Osceola line
    (27.86, -80.88),   # 20 -- western Indian River County
    (27.56, -80.68),   # 21 -- western St. Lucie County
    (27.21, -80.62),   # 22 -- western Martin County (east shore of Lake Okeechobee; Okeechobee city stays out)
    (26.97, -80.62),   # 23 -- northwestern Palm Beach County (Port Mayaca)
    (26.78, -80.88),   # 24 -- western Palm Beach County (Belle Glade / Pahokee in; Clewiston out)
    (26.50, -80.65),   # 25 -- western Broward County (Everglades edge)
    (25.80, -80.70),   # 26 -- western Miami-Dade (Everglades edge)
    (25.30, -80.60),   # 27 -- SW: western Homestead / Florida City
    # polygon closes back to vertex 0
]

SERVICE_COUNTIES = ["Miami-Dade", "Broward", "Palm Beach", "Martin", "St. Lucie", "Indian River", "Brevard"]

EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_in_service_area(lat, lng):
    """Return True if the given coordinates fall inside the service area.

    Performs a fast bounding-box check first, then a ray-casting
    point-in-polygon test against ``SERVICE_AREA_POLYGON``.
    """
    if lat is None or lng is None:
        return False

    lat = float(lat)
    lng = float(lng)

    # --- Fast bounding-box rejection ---
    bounds = SERVICE_AREA_BOUNDS
    if (lat < bounds["south"] or lat > bounds["north"]
            or lng < bounds["west"] or lng > bounds["east"]):
        return False

    # --- Ray-casting point-in-polygon ---
    return _point_in_polygon(lat, lng, SERVICE_AREA_POLYGON)


def distance_to_nearest_boundary(lat, lng):
    """Return the shortest distance in km from the point to the polygon boundary.

    Returns 0.0 if the point is on or outside the polygon.
    A positive value indicates the point is inside the polygon.
    """
    if lat is None or lng is None:
        return 0.0

    lat = float(lat)
    lng = float(lng)

    min_dist = float("inf")
    n = len(SERVICE_AREA_POLYGON)
    for i in range(n):
        p1 = SERVICE_AREA_POLYGON[i]
        p2 = SERVICE_AREA_POLYGON[(i + 1) % n]
        dist = _point_to_segment_distance(lat, lng, p1[0], p1[1], p2[0], p2[1])
        if dist < min_dist:
            min_dist = dist

    return round(min_dist, 2)


def get_service_area_info():
    """Return the full service-area definition for use by the frontend.

    Includes polygon vertices, bounding box, and center coordinates.
    """
    return {
        "polygon": [{"lat": p[0], "lng": p[1]} for p in SERVICE_AREA_POLYGON],
        "bounds": SERVICE_AREA_BOUNDS,
        "center": SERVICE_AREA_CENTER,
        "counties": list(SERVICE_COUNTIES),
        "description": "Florida's Atlantic coast, Homestead to Titusville (seven counties)",
    }


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------

def _point_in_polygon(lat, lng, polygon):
    """Ray-casting algorithm to test if a point is inside a polygon.

    ``polygon`` is a list of (lat, lng) tuples.  The polygon is
    implicitly closed (last vertex connects back to first).
    """
    n = len(polygon)
    inside = False

    px, py = lat, lng
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        # Check if the ray from (px, py) going in +y direction crosses this edge
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside


def _haversine(lat1, lng1, lat2, lng2):
    """Return the great-circle distance in km between two points."""
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def _point_to_segment_distance(px, py, ax, ay, bx, by):
    """Approximate distance in km from point (px, py) to segment (ax, ay)-(bx, by).

    Uses a simple projection onto the line segment and then haversine for
    the final distance calculation.
    """
    # Vector AB
    abx = bx - ax
    aby = by - ay
    # Vector AP
    apx = px - ax
    apy = py - ay

    ab_sq = abx * abx + aby * aby
    if ab_sq == 0:
        # Degenerate segment (A == B)
        return _haversine(px, py, ax, ay)

    # Parameter t of the projection of P onto line AB, clamped to [0, 1]
    t = (apx * abx + apy * aby) / ab_sq
    t = max(0.0, min(1.0, t))

    # Closest point on segment
    closest_lat = ax + t * abx
    closest_lng = ay + t * aby

    return _haversine(px, py, closest_lat, closest_lng)


# ---------------------------------------------------------------------------
# Dynamic coverage — Tier 3-G of the airtight stack
# ---------------------------------------------------------------------------
# The static polygon above says "we serve these 7 counties in principle."
# The dynamic coverage below says "right now, here is where we actually have
# a hauler in range." Both matter — static gates the booking funnel at the
# county level (so out-of-region traffic is rejected outright), dynamic
# gates payment at the address level (so we never charge for an address
# we can't fulfill — wired in routes/booking.py via has_active_coverage).
#
# This function exposes the dynamic state for frontend display so customers
# can see if their address is covered, and so sevs can debug "why was that
# booking blocked / let through" questions visually.

DEFAULT_COVERAGE_RADIUS_MILES = 30.0


def get_dynamic_coverage_summary(radius_miles=DEFAULT_COVERAGE_RADIUS_MILES):
    """Return contractor-derived coverage data for frontend / debugging.

    Returns:
        {
            "contractor_count": int,
            "radius_miles": float,
            "circles": [{"lat": float, "lng": float, "radius_miles": float}],
            # Bounding box around all contractor centers (handy for map fit)
            "bounds": {"north": float, "south": float, "east": float, "west": float} | None,
        }

    Fails open on any DB error (returns an empty summary).
    """
    summary = {
        "contractor_count": 0,
        "radius_miles": radius_miles,
        "circles": [],
        "bounds": None,
    }

    try:
        from models import Contractor
        contractors = Contractor.query.filter_by(approval_status="approved").all()

        lats = []
        lngs = []
        for c in contractors:
            if c.current_lat is None or c.current_lng is None:
                continue
            summary["circles"].append({
                "lat": float(c.current_lat),
                "lng": float(c.current_lng),
                "radius_miles": radius_miles,
            })
            lats.append(float(c.current_lat))
            lngs.append(float(c.current_lng))

        summary["contractor_count"] = len(summary["circles"])

        if lats and lngs:
            summary["bounds"] = {
                "north": max(lats),
                "south": min(lats),
                "east": max(lngs),
                "west": min(lngs),
            }
    except Exception:
        # Fail open — never break frontend rendering on a DB hiccup
        pass

    return summary
