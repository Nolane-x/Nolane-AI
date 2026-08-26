from __future__ import annotations

import json
from pathlib import Path

import pytest

from cogcoder.refoundation.component_versions import component_version
from cogcoder.refoundation.facades import build_active_facade_bindings
from cogcoder.refoundation.implementation_status import (
    ImplementationStatus,
    build_component_implementation_ledger,
)
from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.execution_types import (
    ExecutionAction,
    ExecutionActionKind,
    ExecutionCounters,
    InferenceRequest,
)


def _request(*, checkpoint_digest: str, step_index: int = 0) -> InferenceRequest:
    schema = ("complete",)
    return InferenceRequest(
        agent_id="agent-1",
        neural_version="neural-test-v1",
        task_id="task-1",
        context_digest=canonical_digest({"context": 1}),
        encoder_version="test-encoder-v1",
        checkpoint_digest=checkpoint_digest,
        action_schema=schema,
        action_schema_digest=canonical_digest(list(schema)),
        counters=ExecutionCounters(),
        step_index=step_index,
    )


def test_wave5z_canonical_module_owns_inference_semantics() -> None:
    import nolane.neural.inference_bridge as canonical

    assert canonical.COMPONENT_ID == "neural.inference_bridge"
    assert canonical.COMPONENT_VERSION == "0.0.1"
    assert canonical.MIGRATED_FROM == "cogcoder.organization.execution_inference"

    for value in (
        canonical.AgentInferenceBackend,
        canonical.CognitiveStateEncoder,
        canonical.DeterministicFixtureBackend,
        canonical.R23InferenceBackend,
    ):
        assert value.__module__ == "nolane.neural.inference_bridge"


def test_wave5z_historical_inference_objects_bridge_exact_canonical_identity() -> None:
    import cogcoder.organization.execution_inference as legacy
    import nolane.neural.inference_bridge as canonical

    for name in (
        "AgentInferenceBackend",
        "CognitiveStateEncoder",
        "DeterministicFixtureBackend",
        "R23InferenceBackend",
    ):
        assert getattr(legacy, name) is getattr(canonical, name)

    assert legacy.ACCEPTED_R23_CHECKPOINT_SHA256 == canonical.ACCEPTED_R23_CHECKPOINT_SHA256
    assert legacy.ACCEPTED_R23_VERSION == canonical.ACCEPTED_R23_VERSION


def test_wave5z_import_direction_has_no_reverse_legacy_inference_authority() -> None:
    root = Path(__file__).resolve().parents[1]
    canonical_source = (root / "nolane" / "neural" / "inference_bridge.py").read_text(encoding="utf-8")
    legacy_source = (root / "cogcoder" / "organization" / "execution_inference.py").read_text(encoding="utf-8")
    control_source = (root / "cogcoder" / "organization" / "execution.py").read_text(encoding="utf-8")

    assert "cogcoder.organization.execution_inference" not in canonical_source
    assert "from .execution_inference import" not in control_source
    assert "from nolane.neural.inference_bridge import" in control_source
    assert "nolane.neural.inference_bridge" in legacy_source

    offenders: list[str] = []
    needle = "cogcoder.organization.execution_inference"
    for path in (root / "nolane").rglob("*.py"):
        if path == root / "nolane" / "neural" / "inference_bridge.py":
            continue
        if needle in path.read_text(encoding="utf-8"):
            offenders.append(path.relative_to(root).as_posix())
    assert offenders == []


def test_wave5z_fixture_backend_preserves_fail_closed_deterministic_behavior() -> None:
    from nolane.neural.inference_bridge import DeterministicFixtureBackend

    action = ExecutionAction.complete(reason="done")
    backend = DeterministicFixtureBackend(actions=(action,), checkpoint_digest="fixture-v1")

    first = backend.decide(_request(checkpoint_digest="fixture-v1", step_index=0))
    assert first.action == action

    exhausted = backend.decide(_request(checkpoint_digest="fixture-v1", step_index=1))
    assert exhausted.action.kind is ExecutionActionKind.FAIL
    assert exhausted.action.reason == "fixture action sequence exhausted"

    with pytest.raises(ValueError, match="checkpoint digest"):
        backend.decide(_request(checkpoint_digest="wrong", step_index=0))


def test_wave5z_r23_projection_stream_remains_deterministic_and_bounded() -> None:
    from nolane.neural.inference_bridge import R23InferenceBackend

    first = R23InferenceBackend._stream_floats("seed", 33)
    second = R23InferenceBackend._stream_floats("seed", 33)
    different = R23InferenceBackend._stream_floats("other", 33)

    assert first == second
    assert first != different
    assert len(first) == 33
    assert all(-1.0 <= value <= 1.0 for value in first)


def test_wave5z_authority_version_facade_and_debt_cutover() -> None:
    implementation = build_component_implementation_ledger()
    row = implementation["neural.inference_bridge"]

    assert row.status is ImplementationStatus.CANONICAL_NATIVE
    assert row.canonical_module == "nolane.neural.inference_bridge"
    assert row.canonical_write_authority
    assert row.component_version == "0.0.1"
    assert str(component_version("neural.inference_bridge")) == "0.0.1"
    assert all(
        binding.component_id != "neural.inference_bridge"
        for binding in build_active_facade_bindings()
    )

    control = implementation["external.execution.control"]
    assert control.status is ImplementationStatus.COMPATIBILITY_FACADE

    root = Path(__file__).resolve().parents[1]
    state = json.loads((root / "CURRENT" / "NATIVE_DEBT.json").read_text(encoding="utf-8"))
    serialized = json.dumps(state, sort_keys=True)
    assert "neural.inference_bridge" not in serialized

    non_native = [
        record
        for record in implementation.values()
        if record.status is not ImplementationStatus.CANONICAL_NATIVE
    ]
    assert len(non_native) <= 22


def test_wave5z_current_status_tracks_native_neural_inference_cutover() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "CURRENT" / "STATUS.md").read_text(encoding="utf-8")

    assert "Wave 5Z" in status
    assert "neural.inference_bridge" in status
    assert "22 non-native" in status
