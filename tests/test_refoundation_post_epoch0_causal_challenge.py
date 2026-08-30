from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from nolane.external_core.causal import (
    CausalProgramLedger,
    ComplementaryExperimentProgram,
    InterventionSpec,
)
from nolane.external_core.causal_challenge import (
    CausalAblationEvidence,
    CausalChallengeVerdict,
    CausalHypothesisChallenge,
    bind_causal_hypothesis_challenge,
)
from nolane.external_core.evidence import EvidenceRecord


def _program() -> ComplementaryExperimentProgram:
    left = InterventionSpec(((0, 1.0),))
    right = InterventionSpec(((1, 2.0),))
    interventions = tuple(sorted((left, right), key=lambda row: row.intervention_id))
    payload = {
        "composition_op": "add",
        "interventions": [
            [[int(position), float(value)] for position, value in spec.bindings]
            for spec in interventions
        ],
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return ComplementaryExperimentProgram(
        interventions,
        "add",
        f"exp2.{hashlib.sha256(raw).hexdigest()}",
    )


def _ledger():
    program = _program()
    ledger = CausalProgramLedger("cognitive-library:baseline")
    source = EvidenceRecord(
        "evidence:source-causal",
        "ai.research.source",
        True,
        0,
        0,
        "bounded causal program accepted",
    )
    ledger.register(program, source)
    return ledger, program, source


def _ablation(
    intervention_id: str,
    *,
    evidence_id: str,
    target_reproduced: bool = False,
    verifier: str = "ai.verify.ablation",
) -> CausalAblationEvidence:
    return CausalAblationEvidence(
        removed_intervention_ids=(intervention_id,),
        evidence=EvidenceRecord(evidence_id, verifier, True),
        target_reproduced=target_reproduced,
    )


def _independent() -> tuple[EvidenceRecord, ...]:
    return (EvidenceRecord("evidence:independent-challenge", "ai.verify.challenge", True),)


def test_supported_challenge_binds_exact_ledger_row_and_full_singleton_ablations() -> None:
    ledger, program, _source = _ledger()
    before = ledger.digest
    intervention_ids = tuple(row.intervention_id for row in program.interventions)

    challenge = bind_causal_hypothesis_challenge(
        ledger,
        reasoning_hypothesis_id="hypothesis:reasoning-1",
        program_id=program.program_id,
        ablations=(
            _ablation(intervention_ids[0], evidence_id="evidence:ablation-left"),
            _ablation(intervention_ids[1], evidence_id="evidence:ablation-right"),
        ),
        independent_evidence=_independent(),
        verdict=CausalChallengeVerdict.SUPPORTED,
        reason="both proper subsets fail while independent challenge remains clean",
    )

    assert challenge.reasoning_hypothesis_id == "hypothesis:reasoning-1"
    assert challenge.program_id == program.program_id
    assert challenge.cognitive_library_digest == ledger.cognitive_library_digest
    assert challenge.verdict is CausalChallengeVerdict.SUPPORTED
    assert challenge.proper_subset_coverage == 1.0
    assert challenge.promoted is False
    assert ledger.digest == before
    assert CausalHypothesisChallenge.from_state(challenge.to_state()) == challenge


def test_supported_challenge_requires_every_single_intervention_ablation() -> None:
    ledger, program, _source = _ledger()
    intervention_ids = tuple(row.intervention_id for row in program.interventions)

    with pytest.raises(ValueError, match="proper-subset coverage"):
        bind_causal_hypothesis_challenge(
            ledger,
            reasoning_hypothesis_id="hypothesis:reasoning-1",
            program_id=program.program_id,
            ablations=(
                _ablation(intervention_ids[0], evidence_id="evidence:ablation-left"),
            ),
            independent_evidence=_independent(),
            verdict=CausalChallengeVerdict.SUPPORTED,
            reason="incomplete ablation matrix",
        )


def test_supported_challenge_rejects_reproducing_proper_subset() -> None:
    ledger, program, _source = _ledger()
    intervention_ids = tuple(row.intervention_id for row in program.interventions)

    with pytest.raises(ValueError, match="reproduced"):
        bind_causal_hypothesis_challenge(
            ledger,
            reasoning_hypothesis_id="hypothesis:reasoning-1",
            program_id=program.program_id,
            ablations=(
                _ablation(
                    intervention_ids[0],
                    evidence_id="evidence:ablation-left",
                    target_reproduced=True,
                ),
                _ablation(intervention_ids[1], evidence_id="evidence:ablation-right"),
            ),
            independent_evidence=_independent(),
            verdict=CausalChallengeVerdict.SUPPORTED,
            reason="one proper subset still reproduces target",
        )


def test_falsified_challenge_requires_a_reproducing_proper_subset() -> None:
    ledger, program, _source = _ledger()
    intervention_ids = tuple(row.intervention_id for row in program.interventions)
    ablations = (
        _ablation(
            intervention_ids[0],
            evidence_id="evidence:ablation-left",
            target_reproduced=True,
        ),
        _ablation(intervention_ids[1], evidence_id="evidence:ablation-right"),
    )

    challenge = bind_causal_hypothesis_challenge(
        ledger,
        reasoning_hypothesis_id="hypothesis:reasoning-1",
        program_id=program.program_id,
        ablations=ablations,
        independent_evidence=_independent(),
        verdict=CausalChallengeVerdict.FALSIFIED,
        reason="proper subset reproduced target",
    )
    assert challenge.verdict is CausalChallengeVerdict.FALSIFIED
    assert any(row.target_reproduced for row in challenge.ablations)

    with pytest.raises(ValueError, match="reproducing"):
        bind_causal_hypothesis_challenge(
            ledger,
            reasoning_hypothesis_id="hypothesis:reasoning-2",
            program_id=program.program_id,
            ablations=(
                _ablation(intervention_ids[0], evidence_id="evidence:a"),
                _ablation(intervention_ids[1], evidence_id="evidence:b"),
            ),
            independent_evidence=_independent(),
            verdict=CausalChallengeVerdict.FALSIFIED,
            reason="label alone must not falsify",
        )


def test_challenge_rejects_unplanned_ablation_and_self_verification_loop() -> None:
    ledger, program, source = _ledger()
    intervention_ids = tuple(row.intervention_id for row in program.interventions)
    outsider = InterventionSpec(((2, 3.0),)).intervention_id

    with pytest.raises(ValueError, match="outside causal program"):
        bind_causal_hypothesis_challenge(
            ledger,
            reasoning_hypothesis_id="hypothesis:reasoning-1",
            program_id=program.program_id,
            ablations=(
                _ablation(outsider, evidence_id="evidence:outsider"),
                _ablation(intervention_ids[1], evidence_id="evidence:right"),
            ),
            independent_evidence=_independent(),
            verdict=CausalChallengeVerdict.SUPPORTED,
            reason="outsider must fail closed",
        )

    with pytest.raises(ValueError, match="independent verifier"):
        bind_causal_hypothesis_challenge(
            ledger,
            reasoning_hypothesis_id="hypothesis:reasoning-1",
            program_id=program.program_id,
            ablations=(
                _ablation(intervention_ids[0], evidence_id="evidence:left"),
                _ablation(intervention_ids[1], evidence_id="evidence:right"),
            ),
            independent_evidence=(
                EvidenceRecord("evidence:self", source.verifier_agent_id, True),
            ),
            verdict=CausalChallengeVerdict.SUPPORTED,
            reason="source verifier cannot independently challenge itself",
        )


def test_challenge_requires_clean_evidence_and_known_accepted_program() -> None:
    ledger, program, _source = _ledger()
    intervention_ids = tuple(row.intervention_id for row in program.interventions)
    ablations = (
        _ablation(intervention_ids[0], evidence_id="evidence:left"),
        _ablation(intervention_ids[1], evidence_id="evidence:right"),
    )

    with pytest.raises(ValueError, match="clean passing"):
        bind_causal_hypothesis_challenge(
            ledger,
            reasoning_hypothesis_id="hypothesis:reasoning-1",
            program_id=program.program_id,
            ablations=ablations,
            independent_evidence=(EvidenceRecord("evidence:dirty", "ai.verify.challenge", True, regressions=1),),
            verdict=CausalChallengeVerdict.SUPPORTED,
            reason="dirty evidence must fail closed",
        )

    with pytest.raises(KeyError, match="accepted causal program"):
        bind_causal_hypothesis_challenge(
            ledger,
            reasoning_hypothesis_id="hypothesis:reasoning-1",
            program_id="exp2.unknown",
            ablations=ablations,
            independent_evidence=_independent(),
            verdict=CausalChallengeVerdict.ABSTAIN,
            reason="unknown program",
        )


def test_challenge_restore_rejects_tampered_content_identity() -> None:
    ledger, program, _source = _ledger()
    intervention_ids = tuple(row.intervention_id for row in program.interventions)
    challenge = bind_causal_hypothesis_challenge(
        ledger,
        reasoning_hypothesis_id="hypothesis:reasoning-1",
        program_id=program.program_id,
        ablations=(
            _ablation(intervention_ids[0], evidence_id="evidence:left"),
            _ablation(intervention_ids[1], evidence_id="evidence:right"),
        ),
        independent_evidence=_independent(),
        verdict=CausalChallengeVerdict.SUPPORTED,
        reason="canonical challenge",
    )
    tampered = deepcopy(challenge.to_state())
    tampered["challenge_id"] = "causal-challenge:tampered"

    with pytest.raises(ValueError, match="identity"):
        CausalHypothesisChallenge.from_state(tampered)
