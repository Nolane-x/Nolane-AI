from __future__ import annotations

import pytest

from nolane.metadata.manifests import AgentManifest, build_bootstrap_agent_manifests
from nolane.schemas.identity import AgentIdentity


def _central_identity_state() -> dict[str, object]:
    manifest = next(row for row in build_bootstrap_agent_manifests() if row.rank == "central")
    state = manifest.identity_state()
    assert state["direct_work_capable"] is True
    assert state["learning_capable"] is True
    return state


@pytest.mark.parametrize("field", ("direct_work_capable", "learning_capable"))
@pytest.mark.parametrize("alias", (pytest.param("false", id="string-false"), pytest.param(1, id="integer-one")))
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
@pytest.mark.parametrize("alias", (pytest.param("false", id="string-false"), pytest.param(1, id="integer-one")))
def test_agent_manifest_restore_rejects_non_boolean_permanent_capability_alias(
    field: str,
    alias: object,
) -> None:
    state = _central_identity_state()
    state[field] = alias

    with pytest.raises(
        ValueError,
        match=rf"agent manifest {field} must be exact bool",
    ):
        AgentManifest.from_identity_state(state)
