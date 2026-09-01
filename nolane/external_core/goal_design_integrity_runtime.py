"""Goal/Design integrity runtime with authenticated evolution authority.

The accepted v0.2 runtime is frozen in ``_goal_design_integrity_runtime_v02``.
This v0.3 layer preserves structural lineage/receipt verification while making
permission independently verifiable through an injected capability authority.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from . import _goal_design_integrity_runtime_v02 as _v02
from ._goal_design_integrity_runtime_v02 import *  # noqa: F401,F403
from .goal_design import (
    CoherenceError,
    DesignOption,
    DesignScenario,
    GoalSpec,
    ProofObligation,
    UncertaintyItem,
    stable_digest,
)
from .goal_design_context import (
    DecisionContextContradiction,
    GoalDesignDecisionContext,
    GoalDesignDecisionContextCompiler,
)
from .goal_design_integrity import GoalIntegrityContract
from .goal_design_integrity_evolution import (
    LEGACY_UNATTESTED_TRUST,
    GoalIntegrityEvolutionReceipt,
    verify_goal_integrity_evolution_receipt,
)
from .goal_design_integrity_evolution_authority import (
    GoalIntegrityEvolutionAuthorityVerifier,
)
from .goal_design_runtime import DecisionLifecycle

__version__ = "0.3.2"

VERIFIED_CAPABILITY_AUTHORITY_TRUST = "verified_capability_authority"
LEGACY_UNVERIFIED_AUTHORITY_TRUST = "legacy_unverified_authority"


class GoalIntegrityRuntime(_v02.GoalIntegrityRuntime):
    """v0.3 terminal-integrity runtime with verifier-backed revision authority."""

    AUTHENTICITY_STATE_SCHEMA_VERSION = 3

    def __init__(
        self,
        *args: Any,
        evolution_authority_verifier: GoalIntegrityEvolutionAuthorityVerifier | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.evolution_authority_verifier = evolution_authority_verifier
        self._legacy_unverified_authority_digests: set[str] = set()
        self._verified_capability_evolution_digests: set[str] = set()

    def _ensure_authority_authenticity_state(self) -> None:
        self._ensure_evolution_state()
        if not hasattr(self, "evolution_authority_verifier"):
            self.evolution_authority_verifier = None
        if not hasattr(self, "_legacy_unverified_authority_digests"):
            self._legacy_unverified_authority_digests = set()
        if not hasattr(self, "_verified_capability_evolution_digests"):
            self._verified_capability_evolution_digests = set()

    def install_integrity_contract(
        self,
        contract: GoalIntegrityContract,
        *,
        supersedes_digest: str | None = None,
        evolution_receipt: GoalIntegrityEvolutionReceipt | None = None,
    ) -> str:
        """Install a revision only after structural and live-valid authority proof."""

        self._ensure_authority_authenticity_state()
        current_digest = self._current_contracts.get(contract.goal_id)

        if current_digest is None or current_digest == contract.digest:
            return super().install_integrity_contract(
                contract,
                supersedes_digest=supersedes_digest,
                evolution_receipt=evolution_receipt,
            )

        supplied = "" if supersedes_digest is None else str(supersedes_digest).strip()
        if supplied != current_digest or contract.digest in self._integrity_contracts:
            return super().install_integrity_contract(
                contract,
                supersedes_digest=supersedes_digest,
                evolution_receipt=evolution_receipt,
            )

        if evolution_receipt is None:
            return super().install_integrity_contract(
                contract,
                supersedes_digest=supersedes_digest,
                evolution_receipt=None,
            )

        predecessor = self._integrity_contracts[current_digest]
        try:
            delta = verify_goal_integrity_evolution_receipt(
                evolution_receipt,
                predecessor=predecessor,
                successor=contract,
            )
        except ValueError as exc:
            raise CoherenceError(
                f"Goal/Design integrity evolution authority is invalid: {exc}"
            ) from exc

        verifier = self.evolution_authority_verifier
        if verifier is None:
            raise CoherenceError(
                "Goal/Design integrity evolution requires an authenticity verifier; "
                "a self-asserted authority reference is not a capability proof"
            )
        try:
            verifier.verify_live_authorization_proof(
                evolution_receipt.authority_ref,
                goal_id=contract.goal_id,
                predecessor_digest=predecessor.digest,
                successor_digest=contract.digest,
                delta_digest=delta.digest,
            )
        except ValueError as exc:
            raise CoherenceError(
                f"Goal/Design integrity evolution authority proof is not authentic or live-valid: {exc}"
            ) from exc

        result = super().install_integrity_contract(
            contract,
            supersedes_digest=supersedes_digest,
            evolution_receipt=evolution_receipt,
        )
        self._verified_capability_evolution_digests.add(contract.digest)
        self._legacy_unverified_authority_digests.discard(contract.digest)
        self._legacy_unattested_evolution_digests.discard(contract.digest)
        return result

    def evolution_trust_label(self, contract_digest: str) -> str:
        self._ensure_authority_authenticity_state()
        digest = str(contract_digest).strip()
        if digest in self._verified_capability_evolution_digests:
            return VERIFIED_CAPABILITY_AUTHORITY_TRUST
        if digest in self._legacy_unverified_authority_digests:
            return LEGACY_UNVERIFIED_AUTHORITY_TRUST
        if digest in self._legacy_unattested_evolution_digests:
            return LEGACY_UNATTESTED_TRUST
        raise KeyError(f"contract {digest} is not a Goal/Design integrity revision")

    def compile_decision_context(
        self,
        *,
        receipt_id: str,
        goal: GoalSpec,
        scenarios: Sequence[DesignScenario],
        options: Sequence[DesignOption],
        proof_obligations: Sequence[ProofObligation] = (),
        uncertainties: Sequence[UncertaintyItem] = (),
        contradictions: Sequence[DecisionContextContradiction] = (),
    ) -> GoalDesignDecisionContext:
        """Compile semantic context only from live decision + integrity authority."""

        receipt_id = str(receipt_id).strip()
        try:
            decision_record = self.decisions.get(receipt_id)
        except KeyError as exc:
            raise CoherenceError(
                f"Goal/Design decision context requires known decision authority: {receipt_id}"
            ) from exc
        if decision_record.lifecycle is not DecisionLifecycle.ACTIVE:
            raise CoherenceError(
                "Goal/Design decision context requires active decision authority"
            )

        try:
            integrity_record = self.integrity_authority.get(receipt_id)
        except KeyError as exc:
            raise CoherenceError(
                "Goal/Design decision context requires companion integrity authority"
            ) from exc
        if integrity_record.lifecycle is not DecisionLifecycle.ACTIVE:
            raise CoherenceError(
                "Goal/Design decision context requires active integrity authority"
            )
        if integrity_record.decision_receipt != decision_record.receipt:
            raise CoherenceError(
                "Goal/Design decision context authority records disagree on receipt identity"
            )

        try:
            contract = self.current_integrity_contract(decision_record.receipt.goal_id)
        except KeyError as exc:
            raise CoherenceError(
                "Goal/Design decision context current integrity contract is unavailable"
            ) from exc
        if contract.digest != integrity_record.integrity_receipt.contract_digest:
            raise CoherenceError(
                "Goal/Design decision context integrity contract is stale or superseded"
            )

        try:
            return GoalDesignDecisionContextCompiler().compile(
                decision_receipt=decision_record.receipt,
                integrity_contract=contract,
                integrity_receipt=integrity_record.integrity_receipt,
                goal=goal,
                scenarios=tuple(scenarios),
                options=tuple(options),
                proof_obligations=tuple(proof_obligations),
                uncertainties=tuple(uncertainties),
                contradictions=tuple(contradictions),
            )
        except ValueError as exc:
            raise CoherenceError(
                f"Goal/Design decision context compilation rejected: {exc}"
            ) from exc

    @staticmethod
    def _state_digest_v3(payload: Mapping[str, Any]) -> str:
        return stable_digest({"goal_integrity_runtime_state_v3": dict(payload)})

    def integrity_state(self) -> dict[str, Any]:
        self._ensure_authority_authenticity_state()
        base_state = super().integrity_state()
        payload: dict[str, Any] = {
            "schema_version": self.AUTHENTICITY_STATE_SCHEMA_VERSION,
            "contracts": base_state["contracts"],
            "current_contracts": base_state["current_contracts"],
            "authority": base_state["authority"],
            "evolution_receipts": base_state["evolution_receipts"],
            "legacy_unattested_evolution_digests": tuple(
                sorted(self._legacy_unattested_evolution_digests)
            ),
            "legacy_unverified_authority_digests": tuple(
                sorted(self._legacy_unverified_authority_digests)
            ),
            "verified_capability_evolution_digests": tuple(
                sorted(self._verified_capability_evolution_digests)
            ),
        }
        return {**payload, "state_digest": self._state_digest_v3(payload)}

    @staticmethod
    def _blank_v02_runtime() -> _v02.GoalIntegrityRuntime:
        temporary = _v02.GoalIntegrityRuntime.__new__(_v02.GoalIntegrityRuntime)
        temporary.integrity_authority = _v02.GoalIntegrityAuthorityIndex()
        temporary._integrity_contracts = {}
        temporary._current_contracts = {}
        temporary._contract_predecessors = {}
        temporary._evolution_receipts = {}
        temporary._legacy_unattested_evolution_digests = set()
        return temporary

    @classmethod
    def _restore_v02_temporary(cls, state: Mapping[str, Any]) -> _v02.GoalIntegrityRuntime:
        temporary = cls._blank_v02_runtime()
        temporary.restore_integrity_state(state)
        return temporary

    def restore_integrity_state(self, state: Mapping[str, Any]) -> None:
        """Atomically restore v3, or truthfully migrate historical v1/v2 state."""

        self._ensure_authority_authenticity_state()
        if (
            self._integrity_contracts
            or self._current_contracts
            or self._contract_predecessors
            or self.integrity_authority.records()
            or self._evolution_receipts
            or self._legacy_unattested_evolution_digests
            or self._legacy_unverified_authority_digests
            or self._verified_capability_evolution_digests
        ):
            raise ValueError("Goal/Design integrity runtime state is already populated")

        schema = int(
            state.get(
                "schema_version",
                _v02._base.GoalIntegrityRuntime.INTEGRITY_STATE_SCHEMA_VERSION,
            )
        )

        if schema in (
            _v02._base.GoalIntegrityRuntime.INTEGRITY_STATE_SCHEMA_VERSION,
            _v02.GoalIntegrityRuntime.EVOLUTION_STATE_SCHEMA_VERSION,
        ):
            temporary = self._restore_v02_temporary(state)
            legacy_unattested = set(temporary._legacy_unattested_evolution_digests)
            legacy_unverified = set(temporary._evolution_receipts)
            verified: set[str] = set()
        elif schema == self.AUTHENTICITY_STATE_SCHEMA_VERSION:
            payload: dict[str, Any] = {
                "schema_version": schema,
                "contracts": state.get("contracts", ()),
                "current_contracts": state.get("current_contracts", {}),
                "authority": state.get("authority", {}),
                "evolution_receipts": state.get("evolution_receipts", ()),
                "legacy_unattested_evolution_digests": tuple(
                    state.get("legacy_unattested_evolution_digests", ())
                ),
                "legacy_unverified_authority_digests": tuple(
                    state.get("legacy_unverified_authority_digests", ())
                ),
                "verified_capability_evolution_digests": tuple(
                    state.get("verified_capability_evolution_digests", ())
                ),
            }
            if str(state.get("state_digest", "")) != self._state_digest_v3(payload):
                raise ValueError("Goal/Design integrity runtime v3 state digest mismatch")

            v02_payload = {
                "schema_version": _v02.GoalIntegrityRuntime.EVOLUTION_STATE_SCHEMA_VERSION,
                "contracts": payload["contracts"],
                "current_contracts": payload["current_contracts"],
                "authority": payload["authority"],
                "evolution_receipts": payload["evolution_receipts"],
                "legacy_unattested_evolution_digests": tuple(
                    payload["legacy_unattested_evolution_digests"]
                ),
            }
            v02_state = {
                **v02_payload,
                "state_digest": _v02.GoalIntegrityRuntime._state_digest(v02_payload),
            }
            temporary = self._restore_v02_temporary(v02_state)

            legacy_unattested = {
                str(value) for value in payload["legacy_unattested_evolution_digests"]
            }
            legacy_unverified = {
                str(value) for value in payload["legacy_unverified_authority_digests"]
            }
            verified = {
                str(value) for value in payload["verified_capability_evolution_digests"]
            }
            if legacy_unattested != set(temporary._legacy_unattested_evolution_digests):
                raise ValueError("Goal/Design v3 legacy-unattested provenance does not match topology")
            if legacy_unverified & verified:
                raise ValueError("Goal/Design revision cannot be both legacy-unverified and verified")
            if (legacy_unverified | verified) != set(temporary._evolution_receipts):
                raise ValueError(
                    "every receipted Goal/Design revision requires verified or legacy-unverified provenance"
                )
            revision_digests = {
                digest
                for digest, predecessor in temporary._contract_predecessors.items()
                if predecessor is not None
            }
            if legacy_unattested & (legacy_unverified | verified):
                raise ValueError("Goal/Design revision trust provenance classes must be disjoint")
            if legacy_unattested | legacy_unverified | verified != revision_digests:
                raise ValueError("every Goal/Design revision requires exactly one trust provenance class")

            if verified and self.evolution_authority_verifier is None:
                raise ValueError(
                    "Goal/Design v3 verified revisions require an injected authority authenticity verifier"
                )
            verifier = self.evolution_authority_verifier
            if verifier is not None:
                for digest in sorted(verified):
                    receipt = temporary._evolution_receipts[digest]
                    predecessor_digest = temporary._contract_predecessors[digest]
                    predecessor = temporary._integrity_contracts[predecessor_digest]
                    successor = temporary._integrity_contracts[digest]
                    delta = verify_goal_integrity_evolution_receipt(
                        receipt,
                        predecessor=predecessor,
                        successor=successor,
                    )
                    # Restore validates historical authenticity at proof issuance;
                    # later revocation must not corrupt already committed history.
                    verifier.verify_authorization_proof(
                        receipt.authority_ref,
                        goal_id=successor.goal_id,
                        predecessor_digest=predecessor.digest,
                        successor_digest=successor.digest,
                        delta_digest=delta.digest,
                    )
        else:
            raise ValueError("unsupported Goal/Design integrity runtime schema")

        self._integrity_contracts = dict(temporary._integrity_contracts)
        self._current_contracts = dict(temporary._current_contracts)
        self._contract_predecessors = dict(temporary._contract_predecessors)
        self.integrity_authority = temporary.integrity_authority
        self._evolution_receipts = dict(temporary._evolution_receipts)
        self._legacy_unattested_evolution_digests = set(legacy_unattested)
        self._legacy_unverified_authority_digests = set(legacy_unverified)
        self._verified_capability_evolution_digests = set(verified)


__all__ = tuple(_v02.__all__) + (
    "LEGACY_UNVERIFIED_AUTHORITY_TRUST",
    "VERIFIED_CAPABILITY_AUTHORITY_TRUST",
    "DecisionContextContradiction",
    "GoalDesignDecisionContext",
    "GoalDesignDecisionContextCompiler",
    "GoalIntegrityEvolutionAuthorityVerifier",
    "GoalIntegrityEvolutionReceipt",
    "GoalIntegrityRuntime",
)
