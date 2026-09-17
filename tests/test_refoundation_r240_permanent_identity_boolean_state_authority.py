from __future__ import annotations

import pytest

from nolane.metadata.manifests import build_bootstrap_agent_manifests
from nolane.organization.identity import AgentRegistry
from nolane.schemas.identity import AgentIdentity


def _central_identity_state() -> dict[str, object]:
    manifest = next(row for row in build_bootstrap_agent_manifests() if row.rank == "central")
    state = manifest.identity_state()
    assert state["direct_work_capable"] is True
    assert state["learning_capable"] is True
    return state


@pytest.mark.parametrize("field", ("direct_work_capable", "learning_capable"))
@pytest.mark.parametrize(
    "alias",
    (pytest.param("false", id="string-false"), pytest.param(1, id="integer-one")),
)
def test_agent_identity_restore_rejects_non_boolean_permanent_capability_alias(
    field: str,
    alias: object,
) -> None:
    state = _central_identity_state()
    state[field] = alias

    with pytest.raises(
        ValueError,
        match=rf"permanent identity {field} must be exact bool",
    ):
        AgentIdentity.from_state(state)


@pytest.mark.parametrize("field", ("direct_work_capable", "learning_capable"))
def test_registry_restore_cannot_canonicalize_non_boolean_identity_authority(field: str) -> None:
    state = _central_identity_state()
    state[field] = "false"

    with pytest.raises(
        ValueError,
        match=rf"permanent identity {field} must be exact bool",
    ):
        AgentRegistry.from_state({"identities": [state]})
