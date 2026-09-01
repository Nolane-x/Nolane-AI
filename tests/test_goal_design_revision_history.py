from nolane.external_core.goal_design_integrity import (
    GoalIntegrityClause,
    GoalIntegrityClauseKind,
    GoalIntegrityContract,
)
from nolane.external_core.goal_design_integrity_evolution import (
    mint_verified_goal_integrity_evolution_receipt,
)
from nolane.external_core.goal_design_integrity_evolution_authority import (
    GOAL_INTEGRITY_EVOLUTION_ACTION,
    GoalIntegrityEvolutionAuthorityVerifier,
)
from nolane.external_core.goal_design_integrity_runtime import (
    GoalIntegrityAuthorityIndex,
    GoalIntegrityRuntime,
)

_AUTHORITY_KEY = b"revision-history-authority-key-32"
_GOAL_ID = "goal:revision-history"


class _Clock:
    def __init__(self, value: int = 100) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value


def _contract(statement: str) -> GoalIntegrityContract:
    return GoalIntegrityContract(
        goal_id=_GOAL_ID,
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                _GOAL_ID,
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                statement,
                "prov:reviewed-user-intent",
            ),
            GoalIntegrityClause(
                "constraint:user-control",
                _GOAL_ID,
                GoalIntegrityClauseKind.HARD_CONSTRAINT,
                "Preserve explicit user control.",
                "prov:user-control",
            ),
        ),
    )


def _verifier():
    verifier = GoalIntegrityEvolutionAuthorityVerifier(
        trusted_root_issuers=("authority:root",),
        authority_key=_AUTHORITY_KEY,
        clock=_Clock(),
    )
    grant = verifier.issue_root_grant(
        issuer_ref="authority:root",
        subject_ref="authority:goal-owner",
        goal_ids=(_GOAL_ID,),
        actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
        valid_from_epoch_s=50,
        valid_until_epoch_s=500,
    )
    return verifier, grant


def _blank_runtime(verifier) -> GoalIntegrityRuntime:
    runtime = GoalIntegrityRuntime.__new__(GoalIntegrityRuntime)
    runtime.integrity_authority = GoalIntegrityAuthorityIndex()
    runtime._integrity_contracts = {}
    runtime._current_contracts = {}
    runtime._contract_predecessors = {}
    runtime._evolution_receipts = {}
    runtime._legacy_unattested_evolution_digests = set()
    runtime._legacy_unverified_authority_digests = set()
    runtime._verified_capability_evolution_digests = set()
    runtime.evolution_authority_verifier = verifier
    return runtime


def _verified_revision_runtime():
    verifier, grant = _verifier()
    runtime = _blank_runtime(verifier)
    original = _contract("Preserve explicit terminal intent.")
    revised = _contract("Preserve the reviewed revised terminal intent.")
    proof = verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=original,
        successor=revised,
    )
    receipt = mint_verified_goal_integrity_evolution_receipt(
        predecessor=original,
        successor=revised,
        authorization_proof=proof,
        reason="Reviewed Goal/Design revision for public history projection.",
        source_refs=("source:reviewed-intent",),
        evidence_refs=("evidence:authority-proof",),
        freshness_ref="freshness:revision-100",
        confidence_milli=940,
    )
    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=receipt,
    )
    return runtime, original, revised, receipt


def test_runtime_exports_typed_verified_goal_revision_history():
    runtime, original, revised, receipt = _verified_revision_runtime()

    history = runtime.goal_revision_history(original.goal_id)

    assert history.snapshot.current_contract_digest == revised.digest
    assert tuple(entry.contract_digest for entry in history.snapshot.entries) == (
        original.digest,
        revised.digest,
    )
    assert history.snapshot.entries[1].evolution_receipt_id == receipt.receipt_id
    assert history.snapshot.entries[1].freshness_ref == receipt.freshness_ref
    assert history.snapshot.entries[1].confidence_milli == receipt.confidence_milli
    assert history.receipt.receipt_id
