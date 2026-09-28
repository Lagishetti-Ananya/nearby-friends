"""Full location-update flow. Requires a running Compose stack."""

import os

import pytest

pytestmark = pytest.mark.skipif(not os.getenv("RUN_INTEGRATION"), reason="needs live stack")


def test_e2e_module_runs():
    import asyncio

    from e2e_check import main

    assert asyncio.run(main()) == 0
