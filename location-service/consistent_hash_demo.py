"""Print remap statistics when adding/removing consistent-hash nodes."""

from __future__ import annotations

from consistent_hash import HashRing, remap_fraction


def demo() -> None:
    keys = [f"user:{i}" for i in range(10_000)]
    ring = HashRing(["redis-1", "redis-2", "redis-3"])
    before = {k: ring.get_node(k) for k in keys}
    ring.add_node("redis-4")
    changed = sum(1 for k, node in before.items() if ring.get_node(k) != node)
    print(f"Keys: {len(keys)}")
    print(f"Nodes after add: {ring.nodes}")
    print(f"Remapped after adding redis-4: {changed} ({changed / len(keys):.1%})")
    print("Expected around 1/4 remapped with virtual nodes.")
    ring.remove_node("redis-2")
    print(f"Nodes after remove redis-2: {ring.nodes}")
    frac = remap_fraction(HashRing(["redis-1", "redis-3", "redis-4"]), ring, keys)
    print(f"Identity remap vs rebuilt ring: {frac:.1%} (should be ~0)")


if __name__ == "__main__":
    demo()
