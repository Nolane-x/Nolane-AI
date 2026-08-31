"""Goal/Design integrity evolution protocol with authenticated authority proofs.

The accepted v0.1 structural receipt protocol is frozen in
``_goal_design_integrity_evolution_v01``. This public layer preserves all v0.1
receipt identities while adding a proof-bound minting path. Runtime acceptance
still requires an independent authority verifier; a proof-shaped object alone
is never permission.
"""
from __future__ import annotations

from typing import Iterable

from . import _goal_design_integrity_evolution_v01 as _v01
from ._goal_design_integrity_evolution_v01 import *  # noqa: F401,F403
from .goal_design_integrity import GoalIntegrityContract
from .goal_design_integrity_evolution_authority import (
    GOAL_INTEGRITY_EVOLUTION_ACTION,
    GoalIntegrityEvolutionAuthorizationProof,
)

__version__ = "0.2.0"


def mint_verified_goal_integrity_evolution_receipt(
    *,
    predecessor: GoalIntegrityContract,
    successor: GoalIntegrityContract,
    authorization_proof: GoalIntegrityEvolutionAuthorizationProof,
    reason: str,
    source_refs: Iterable[str],
    evidence_refs: Iterable[str],
    freshness_ref: str,
    confidence_milli: int = 1000,
) -> GoalIntegrityEvolutionReceipt:
    """Bind a structural evolution receipt to one verifier-issued proof ID.

    This function checks deterministic transition equality only. Authenticity of
    ``authorization_proof`` is deliberately not inferred from its dataclass
    shape; ``GoalIntegrityRuntime`` resolves the proof ID through its injected
    verifier before any state mutation.
    """

    delta = assess_goal_integrity_evolution(predecessor, successor)
    if authorization_proof.action != GOAL_INTEGRITY_EVOLUTION_ACTION:
        raise ValueError("Goal/Design evolution proof action mismatch")
    bindings = (
        ("goal", authorization_proof.goal_id, predecessor.goal_id),
        ("predecessor", authorization_proof.predecessor_digest, predecessor.digest),
        ("successor", authorization_proof.successor_digest, successor.digest),
        ("delta", authorization_proof.delta_digest, delta.digest),
    )
    for name, actual, expected in bindings:
        if actual != expected:
            raise ValueError(f"Goal/Design evolution proof {name} does not bind transition")
    return mint_goal_integrity_evolution_receipt(
        predecessor=predecessor,
        successor=successor,
        authority_ref=authorization_proof.proof_id,
        reason=reason,
        source_refs=source_refs,
        evidence_refs=evidence_refs,
        freshness_ref=freshness_ref,
        confidence_milli=confidence_milli,
    )


__all__ = tuple(_v01.__all__) + (
    "GOAL_INTEGRITY_EVOLUTION_ACTION",
    "GoalIntegrityEvolutionAuthorizationProof",
    "mint_verified_goal_integrity_evolution_receipt",
)
