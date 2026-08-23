from __future__ import annotations

from typing import Any, Mapping, TypeAlias

from cogcoder.organization.runtime import OrganizationRuntime


# Epoch 0 permits exactly this module to cross into the accepted historical
# runtime inheritance chain. Canonical modules import the semantic alias below
# rather than importing ``cogcoder.organization.runtime`` directly.
AcceptedOrganizationRuntime: TypeAlias = OrganizationRuntime


def restore_accepted_runtime(state: Mapping[str, Any]) -> AcceptedOrganizationRuntime:
    return OrganizationRuntime.from_state(state)


__all__ = ("AcceptedOrganizationRuntime", "restore_accepted_runtime")
