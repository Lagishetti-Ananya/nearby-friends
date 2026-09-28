"""Keep the spec's redis/ directory from shadowing the redis-py package."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [p for p in sys.path if Path(p).resolve() != ROOT.resolve()]
# simulation first so `import metrics` is the load simulator, not Redis helpers.
for extra in (ROOT / "redis", ROOT / "location-service", ROOT / "simulation"):
    s = str(extra)
    if s in sys.path:
        sys.path.remove(s)
    sys.path.insert(0, s)
