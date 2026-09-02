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


_AUTHORITY_KEY = b"revision-history-authority-key-32b"


class _Clock:
    def __init__(self, value: int = 100) -> None:
        self.value = value

    def __call__(self) -> int:
        return self.value


def _contract(statement: str) -> GoalIntegrityContract:
    goal_id = "goal:revision-history"
    return GoalIntegrityContract(
        goal_id=goal_id,
        clauses=(
            GoalIntegrityClause(
                "intent:terminal",
                goal_id,
                GoalIntegrityClauseKind.TERMINAL_GOAL,
                statement,
                "provenance:terminal-intent",
            ),
            GoalIntegrityClause(
                "constraint:traceable",
                goal_id,
                GoalIntegrityClauseKind.HARD_CONSTRAINT,
                "Every accepted goal revision remains traceable to exact authority evidence.",
                "provenance:traceability",
            ),
        ),
    )


def _runtime_with_verified_revision():
    clock = _Clock()
    verifier = GoalIntegrityEvolutionAuthorityVerifier(
        trusted_root_issuers=("authority:root",),
        authority_key=_AUTHORITY_KEY,
        clock=clock,
    )
    grant = verifier.issue_root_grant(
        issuer_ref="authority:root",
        subject_ref="authority:goal-owner",
        goal_ids=("goal:revision-history",),
        actions=(GOAL_INTEGRITY_EVOLUTION_ACTION,),
        valid_from_epoch_s=50,
        valid_until_epoch_s=500,
    )

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

    original = _contract("Preserve the user's explicit terminal intent.")
    revised = _contract("Preserve the user's reviewed revised terminal intent.")
    proof = verifier.authorize_contract_transition(
        grant.grant_id,
        predecessor=original,
        successor=revised,
    )
    receipt = mint_verified_goal_integrity_evolution_receipt(
        predecessor=original,
        successor=revised,
        authorization_proof=proof,
        reason="Reviewed terminal-intent revision with explicit authorization.",
        source_refs=("source:user-reviewed-revision",),
        evidence_refs=("evidence:review-record", "evidence:authority-proof"),
        freshness_ref="freshness:reviewed-at-authority-boundary",
        confidence_milli=930,
    )

    runtime.install_integrity_contract(original)
    runtime.install_integrity_contract(
        revised,
        supersedes_digest=original.digest,
        evolution_receipt=receipt,
    )
    return runtime, original, revised, receipt


def test_runtime_projects_deterministic_public_goal_revision_history():
    runtime, original, revised, receipt = _runtime_with_verified_revision()

    history = runtime.goal_revision_history(original.goal_id)

    assert history.goal_id == original.goal_id
    assert history.current_contract_digest == revised.digest
    assert tuple(entry.contract_digest for entry in history.entries) == (
        original.digest,
        revised.digest,
    )
    assert history.entries[-1].evolution_receipt_id == receipt.receipt_id
