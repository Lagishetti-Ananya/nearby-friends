from distance import haversine_miles, within_radius


def test_haversine_zero():
    assert haversine_miles(37.77, -122.42, 37.77, -122.42) == 0


def test_sf_to_oakland_ballpark():
    miles = haversine_miles(37.7749, -122.4194, 37.8044, -122.2711)
    assert 7 < miles < 11


def test_radius_filter():
    assert within_radius(37.7749, -122.4194, 37.7840, -122.4094, 5)
    assert not within_radius(37.7749, -122.4194, 37.3382, -121.8863, 10)
