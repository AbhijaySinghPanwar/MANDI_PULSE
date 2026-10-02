"""Haversine against geopy's WGS-84 geodesic distance (an independent reference)."""

import pytest
from geopy.distance import geodesic

from mandipulse.geo.distance import haversine_km

CITY_PAIRS = {
    # name: ((lat, lon), (lat, lon))
    "Mumbai-Pune": ((19.0760, 72.8777), (18.5204, 73.8567)),
    "Nashik-Pune": ((19.9975, 73.7898), (18.5204, 73.8567)),
    "Indore-Bhopal": ((22.7196, 75.8577), (23.2599, 77.4126)),
    "Lucknow-Kanpur": ((26.8467, 80.9462), (26.4499, 80.3319)),
    "Ahmedabad-Delhi": ((23.0225, 72.5714), (28.6139, 77.2090)),
}


@pytest.mark.parametrize("pair", CITY_PAIRS)
def test_haversine_within_1pct_of_geodesic(pair):
    a, b = CITY_PAIRS[pair]
    expected = geodesic(a, b).km
    assert haversine_km(*a, *b) == pytest.approx(expected, rel=0.01)


def test_zero_distance_and_symmetry():
    assert haversine_km(19.0, 73.0, 19.0, 73.0) == 0
    a, b = CITY_PAIRS["Mumbai-Pune"]
    assert haversine_km(*a, *b) == pytest.approx(haversine_km(*b, *a))


def test_one_degree_of_latitude_is_about_111_km():
    assert haversine_km(20.0, 75.0, 21.0, 75.0) == pytest.approx(111.2, abs=0.1)
