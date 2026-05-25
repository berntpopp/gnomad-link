from __future__ import annotations

import pytest


@pytest.fixture
def fake_service_factory():
    def factory():
        raise AssertionError(
            "Surface tests must not invoke the gnomAD service; "
            "tests that need a stub service should override this fixture."
        )

    return factory
