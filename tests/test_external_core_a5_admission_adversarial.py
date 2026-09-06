from __future__ import annotations

import pytest

from nolane.external_core.integration_admission import CanonicalAdmissionContext


class _StringLaunderer:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


def _kwargs() -> dict[str, object]:
    return {
        "registry_digest": "registry-v1-test",
        "authority_graph_digest": "graph-v1-test",
        "source_state_frontier_digest": "source-frontier-test",
        "evidence_frontier_digest": "evidence-frontier-test",
        "artifact_frontier_digest": "artifact-frontier-test",
        "freshness_fence_frontier_digest": "freshness-frontier-test",
        "handoff_frontier_digest": "handoff-frontier-test",
        "work_trace_frontier_digest": "trace-frontier-test",
        "observed_epoch": 3,
    }


@pytest.mark.parametrize(
    "field",
    (
        "registry_digest",
        "authority_graph_digest",
        "source_state_frontier_digest",
        "evidence_frontier_digest",
        "artifact_frontier_digest",
        "freshness_fence_frontier_digest",
        "handoff_frontier_digest",
        "work_trace_frontier_digest",
    ),
)
def test_current_admission_rejects_custom_str_laundering(field: str) -> None:
    kwargs = _kwargs()
    kwargs[field] = _StringLaunderer(str(kwargs[field]))
    with pytest.raises(ValueError, match="explicit string"):
        CanonicalAdmissionContext.create(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize("epoch", (True, False, 1.0, "1", -1))
def test_current_admission_rejects_non_exact_epoch(epoch: object) -> None:
    kwargs = _kwargs()
    kwargs["observed_epoch"] = epoch
    with pytest.raises(ValueError, match="non-negative integer"):
        CanonicalAdmissionContext.create(**kwargs)  # type: ignore[arg-type]


def test_current_admission_restore_rejects_protocol_object_even_if_stringifies_correctly() -> None:
    context = CanonicalAdmissionContext.create(**_kwargs())  # type: ignore[arg-type]
    state = context.to_state()
    state["protocol"] = _StringLaunderer(state["protocol"])
    with pytest.raises(ValueError, match="protocol"):
        CanonicalAdmissionContext.from_state(state)
