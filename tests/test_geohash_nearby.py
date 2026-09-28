from datetime import datetime, timezone

from geohash import candidate_cells, decode, encode, in_candidate_cells, neighbors
from nearby import LocatedUser, select_nearby


def test_encode_stable():
    h = encode(37.7749, -122.4194, 5)
    assert len(h) == 5
    assert h == encode(37.7749, -122.4194, 5)


def test_neighbors_include_center_and_eight():
    h = encode(37.7749, -122.4194, 5)
    cells = neighbors(h)
    assert h in cells
    assert 8 <= len(cells) <= 9


def test_neighbor_cell_centers_are_candidates():
    h = encode(37.7749, -122.4194, 5)
    cells = neighbors(h)
    for cell in cells:
        lat, lon = decode(cell)
        assert in_candidate_cells(encode(lat, lon, 5), cells)


def test_nearby_radius_and_paging():
    origin = (37.7749, -122.4194)
    friends = []
    for i, (lat, lon, name) in enumerate(
        [
            (37.7840, -122.4094, "Bob"),
            (37.7649, -122.4294, "Carol"),
            (37.3382, -121.8863, "Eve"),
        ]
    ):
        friends.append(
            LocatedUser(
                user_id=str(i),
                name=name,
                latitude=lat,
                longitude=lon,
                updated_at=datetime.now(timezone.utc),
                geohash=encode(lat, lon, 5),
            )
        )
    page, total = select_nearby(*origin, "me", friends, radius_miles=5, page=1, page_size=20)
    names = {f.name for f in page}
    assert "Eve" not in names
    assert "Bob" in names
    assert total == len(page)
    page2, total2 = select_nearby(*origin, "me", friends, radius_miles=5, page=1, page_size=1)
    assert len(page2) == 1
    assert total2 >= 1
