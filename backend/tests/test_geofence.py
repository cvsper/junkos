"""The service area runs up the coast to Brevard — and no further."""
import pytest

from geofencing import is_in_service_area, get_service_area_info, SERVICE_COUNTIES

INSIDE = {
    "Homestead": (25.47, -80.45), "Miami Beach": (25.79, -80.13), "Hialeah": (25.86, -80.28),
    "Fort Lauderdale": (26.12, -80.14), "Davie": (26.07, -80.25), "Boca Raton": (26.37, -80.10),
    "Lantana": (26.59, -80.05), "West Palm Beach": (26.71, -80.06), "Wellington": (26.66, -80.27),
    "Jupiter": (26.93, -80.10), "Stuart": (27.20, -80.25), "Palm City": (27.17, -80.27),
    "Port St. Lucie": (27.29, -80.35), "Fort Pierce": (27.45, -80.33), "Vero Beach": (27.64, -80.40),
    "Sebastian": (27.82, -80.47), "Melbourne": (28.08, -80.61), "Palm Bay": (28.03, -80.62),
    "Cocoa Beach": (28.32, -80.61), "Cocoa": (28.39, -80.75), "Merritt Island": (28.36, -80.68),
    "Titusville": (28.61, -80.81), "Belle Glade": (26.68, -80.67), "Pahokee": (26.82, -80.66),
}
OUTSIDE = {
    "Orlando": (28.54, -81.38), "Kissimmee": (28.30, -81.41), "Okeechobee": (27.24, -80.83),
    "Daytona Beach": (29.21, -81.02), "Key Largo": (25.09, -80.45), "Naples": (26.14, -81.79),
    "Clewiston": (26.75, -80.93), "New York": (40.71, -74.01),
}


@pytest.mark.parametrize("city,pt", INSIDE.items())
def test_coastal_cities_up_to_titusville_are_inside(city, pt):
    assert is_in_service_area(*pt), city


@pytest.mark.parametrize("city,pt", OUTSIDE.items())
def test_inland_and_far_cities_stay_outside(city, pt):
    assert not is_in_service_area(*pt), city


def test_info_names_all_seven_counties(client):
    assert len(SERVICE_COUNTIES) == 7 and "Brevard" in SERVICE_COUNTIES
    body = client.get("/api/service-area").get_json()["service_area"]
    assert body["counties"] == SERVICE_COUNTIES and body["bounds"]["north"] == 28.80
    r = client.post("/api/service-area/check", json={"lat": 28.32, "lng": -80.61}).get_json()
    assert r["in_service_area"] is True
    r = client.post("/api/service-area/check", json={"lat": 28.54, "lng": -81.38}).get_json()
    assert r["in_service_area"] is False and "Brevard" in r["message"]
