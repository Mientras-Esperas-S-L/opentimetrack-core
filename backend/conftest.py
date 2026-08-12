"""Shared test setup."""

from __future__ import annotations

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _empty_rate_limit_buckets():
    """Each test starts with the throttle counters at zero.

    Rate limiting counts in the cache, and the cache does not roll back with
    the transaction. Without this, the fifth test to sign in within a minute
    gets a 429 and the failure reads like a broken login --- and worse, the
    order of the suite starts deciding which tests pass.

    Cleared rather than disabled: a test that wants to prove the limit works
    should be able to, and one that merely signs in should not spend somebody
    else's budget.
    """
    cache.clear()
    yield
