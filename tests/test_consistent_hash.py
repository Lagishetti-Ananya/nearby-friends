from consistent_hash import HashRing, remap_fraction


def test_same_key_stable():
    ring = HashRing(["a", "b", "c"])
    assert ring.get_node("user:42") == ring.get_node("user:42")


def test_add_node_minimizes_remap():
    keys = [f"ch:{i}" for i in range(5000)]
    old = HashRing(["n1", "n2", "n3"])
    new = HashRing(["n1", "n2", "n3", "n4"])
    frac = remap_fraction(old, new, keys)
    assert 0.05 < frac < 0.45


def test_empty_ring():
    assert HashRing([]).get_node("x") is None
