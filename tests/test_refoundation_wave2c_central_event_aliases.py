from __future__ import annotations

from cogcoder.organization.types import EventKind


def test_central_eventkind_compatibility_aliases_are_preserved() -> None:
    import nolane.organization.central  # noqa: F401 - registers accepted compatibility aliases

    for name in (
        "CENTRAL_RESOURCE_ALLOCATED",
        "CENTRAL_RESOURCE_RELEASED",
        "CENTRAL_CONFLICT_OPENED",
        "CENTRAL_CONFLICT_RESOLVED",
        "CENTRAL_DIRECT_WORK",
        "CENTRAL_CORE_LEASE_GRANTED",
        "CENTRAL_CORE_LEASE_REVOKED",
    ):
        assert getattr(EventKind, name) is EventKind.CENTRAL_INTERVENTION
