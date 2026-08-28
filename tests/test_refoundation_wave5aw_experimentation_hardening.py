from __future__ import annotations

import pytest

from nolane.external_core.evidence import EvidenceRecord
from nolane.external_core.experimentation import (
    ExperimentHypothesis,
    ExperimentLedger,
    ExperimentProbe,
    ShadowExperimentReceipt,
    VersionSpace,
    run_shadow_experiment,
)


def _probes(values=(-1, 0, 1)) -> tuple[ExperimentProbe, ...]:
    return tuple(ExperimentProbe((x, y)) for x in values for y in values)


def _hypothesis(
    probes: tuple[ExperimentProbe, ...],
    fn,
    *,
    display_name: str,
) -> ExperimentHypothesis:
    return ExperimentHypothesis(
        tuple((probe.probe_id, fn(*probe.args)) for probe in probes),
        display_name=display_name,
    )


def test_wave5aw_accept_receipt_cannot_be_forged_without_independent_verification() -> None:
    probe = ExperimentProbe((0, 0))
    selected = ExperimentHypothesis(((probe.probe_id, 0),), display_name="candidate")

    with pytest.raises(ValueError, match="verification"):
        ShadowExperimentReceipt(
            "xexp:forged",
            "accept",
            selected,
            1,
            1,
            0,
            0,
            (),
            0,
            "shadow_experiment_verified",
        )


def test_wave5aw_ledger_is_idempotent_across_nonsemantic_hypothesis_renames() -> None:
    selection = _probes((-1, 0, 1))
    verification = _probes((-2, 2))
    domain = tuple({probe.probe_id: probe for probe in (*selection, *verification)}.values())

    first_space = VersionSpace(
        (
            _hypothesis(domain, lambda x, y: x + y, display_name="add"),
            _hypothesis(domain, lambda x, y: x - y, display_name="subtract"),
        )
    )
    renamed_space = VersionSpace(
        (
            _hypothesis(domain, lambda x, y: x + y, display_name="human-label-renamed"),
            _hypothesis(domain, lambda x, y: x - y, display_name="another-label"),
        )
    )

    oracle = lambda probe: probe.args[0] + probe.args[1]
    first = run_shadow_experiment(
        first_space,
        selection,
        oracle,
        verification_probes=verification,
        max_selection_oracle_calls=1,
    )
    renamed = run_shadow_experiment(
        renamed_space,
        selection,
        oracle,
        verification_probes=verification,
        max_selection_oracle_calls=1,
    )
    assert first.status == renamed.status == "accept"
    assert first.experiment_id == renamed.experiment_id
    assert first.selected is not None and renamed.selected is not None
    assert first.selected.hypothesis_id == renamed.selected.hypothesis_id

    evidence = EvidenceRecord("wave5aw-rename", "ai.research.1", True, 0, 0, "rename-stable semantic receipt")
    ledger = ExperimentLedger("causal-basis:test")
    first_record = ledger.register(first, evidence)
    renamed_record = ledger.register(renamed, evidence)

    assert renamed_record == first_record
    assert len(ledger.records) == 1
