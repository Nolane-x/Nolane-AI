"""Goal/Design integrity runtime with explicit contract-evolution authority.

The v0.1 runtime is frozen in ``_goal_design_integrity_runtime_v01``. This
module preserves that authority surface while adding restart-verifiable,
content-addressed permission for every non-root contract revision.
"""
from __future__ import annotations

from typing import Any, Mapping

from . import _goal_design_integrity_runtime_v01 as _base
from ._goal_design_integrity_runtime_v01 import *  # noqa: F401,F403
from .goal_design import CoherenceError, stable_digest
from .goal_design_integrity import GoalIntegrityContract
from .goal_design_integrity_evolution import (
    EXPLICIT_EVOLUTION_TRUST,
    LEGACY_UNATTESTED_TRUST,
    GoalIntegrityEvolutionReceipt,
    goal_integrity_evolution_receipt_from_state,
    goal_integrity_evolution_receipt_to_state,
    verify_goal_integrity_evolution_receipt,
)

__version__ = "0.2.0"


class GoalIntegrityRuntime(_base.GoalIntegrityRuntime):
    """v0.2 terminal-integrity runtime with explicit revision authority."""

    EVOLUTION_STATE_SCHEMA_VERSION = 2

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._evolution_receipts: dict[str, GoalIntegrityEvolutionReceipt] = {}
        self._legacy_unattested_evolution_digests: set[str] = set()

    def _ensure_evolution_state(self) -> None:
        # Some authority tests intentionally construct the bounded integrity
        # layer with __new__ and no five-plane runtime. Keep that seam valid.
        if not hasattr(self, "_evolution_receipts"):
            self._evolution_receipts = {}
        if not hasattr(self, "_legacy_unattested_evolution_digests"):
            self._legacy_unattested_evolution_digests = set()

    def install_integrity_contract(
        self,
        contract: GoalIntegrityContract,
        *,
        supersedes_digest: str | None = None,
        evolution_receipt: GoalIntegrityEvolutionReceipt | None = None,
    ) -> str:
        """Install root authority or supersede only with exact evolution proof."""

        self._ensure_evolution_state()
        current_digest = self._current_contracts.get(contract.goal_id)

        if current_digest is None or current_digest == contract.digest:
            if evolution_receipt is not None:
                raise CoherenceError(
                    "Goal/Design evolution authority is only valid for a changed non-root contract"
                )
            return super().install_integrity_contract(
                contract,
                supersedes_digest=supersedes_digest,
            )

        # Preserve the v0.1 ordering for lineage errors and historical replay:
        # a caller cannot hide a wrong predecessor behind a missing receipt.
        supplied = "" if supersedes_digest is None else str(supersedes_digest).strip()
        if supplied != current_digest or contract.digest in self._integrity_contracts:
            return super().install_integrity_contract(
                contract,
                supersedes_digest=supersedes_digest,
            )

        if evolution_receipt is None:
            raise CoherenceError(
                "Goal/Design integrity contract evolution requires explicit evolution authority; "
                "an exact predecessor digest proves lineage but cannot authorize semantic revision"
            )

        predecessor = self._integrity_contracts[current_digest]
        try:
            verify_goal_integrity_evolution_receipt(
                evolution_receipt,
                predecessor=predecessor,
                successor=contract,
            )
        except ValueError as exc:
            raise CoherenceError(
                f"Goal/Design integrity evolution authority is invalid: {exc}"
            ) from exc

        result = super().install_integrity_contract(
            contract,
            supersedes_digest=supersedes_digest,
        )
        self._evolution_receipts[contract.digest] = evolution_receipt
        self._legacy_unattested_evolution_digests.discard(contract.digest)
        return result

    def evolution_receipt_for(self, contract_digest: str) -> GoalIntegrityEvolutionReceipt:
        self._ensure_evolution_state()
        digest = str(contract_digest).strip()
        try:
            return self._evolution_receipts[digest]
        except KeyError as exc:
            raise KeyError(f"no explicit Goal/Design evolution receipt for {digest}") from exc

    def evolution_trust_label(self, contract_digest: str) -> str:
        self._ensure_evolution_state()
        digest = str(contract_digest).strip()
        if digest in self._evolution_receipts:
            return EXPLICIT_EVOLUTION_TRUST
        if digest in self._legacy_unattested_evolution_digests:
            return LEGACY_UNATTESTED_TRUST
        raise KeyError(f"contract {digest} is not a Goal/Design integrity revision")

    @staticmethod
    def _state_digest(payload: Mapping[str, Any]) -> str:
        return stable_digest({"goal_integrity_runtime_state_v2": dict(payload)})

    def integrity_state(self) -> dict[str, Any]:
        self._ensure_evolution_state()
        base_state = super().integrity_state()
        payload: dict[str, Any] = {
            "schema_version": self.EVOLUTION_STATE_SCHEMA_VERSION,
            "contracts": base_state["contracts"],
            "current_contracts": base_state["current_contracts"],
            "authority": base_state["authority"],
            "evolution_receipts": [
                {
                    "successor_digest": digest,
                    "receipt": goal_integrity_evolution_receipt_to_state(
                        self._evolution_receipts[digest]
                    ),
                }
                for digest in sorted(self._evolution_receipts)
            ],
            "legacy_unattested_evolution_digests": tuple(
                sorted(self._legacy_unattested_evolution_digests)
            ),
        }
        return {**payload, "state_digest": self._state_digest(payload)}

    @staticmethod
    def _validated_base_runtime(state: Mapping[str, Any]) -> _base.GoalIntegrityRuntime:
        temporary = _base.GoalIntegrityRuntime.__new__(_base.GoalIntegrityRuntime)
        temporary.integrity_authority = _base.GoalIntegrityAuthorityIndex()
        temporary._integrity_contracts = {}
        temporary._current_contracts = {}
        temporary._contract_predecessors = {}
        temporary.restore_integrity_state(state)
        return temporary

    def restore_integrity_state(self, state: Mapping[str, Any]) -> None:
        """Atomically restore v2 authority, or explicitly migrate historical v1."""

        self._ensure_evolution_state()
        if (
            self._integrity_contracts
            or self._current_contracts
            or self._contract_predecessors
            or self.integrity_authority.records()
            or self._evolution_receipts
            or self._legacy_unattested_evolution_digests
        ):
            raise ValueError("Goal/Design integrity runtime state is already populated")

        schema = int(state.get("schema_version", _base.GoalIntegrityRuntime.INTEGRITY_STATE_SCHEMA_VERSION))
        if schema == _base.GoalIntegrityRuntime.INTEGRITY_STATE_SCHEMA_VERSION:
            # Historical state predates evolution receipts. Preserve it without
            # fabricating evidence, and make that trust boundary explicit on the
            # first v2 reserialization.
            temporary = self._validated_base_runtime(state)
            receipts: dict[str, GoalIntegrityEvolutionReceipt] = {}
            legacy = {
                digest
                for digest, predecessor in temporary._contract_predecessors.items()
                if predecessor is not None
            }
        elif schema == self.EVOLUTION_STATE_SCHEMA_VERSION:
            payload = {
                "schema_version": schema,
                "contracts": state.get("contracts", ()),
                "current_contracts": state.get("current_contracts", {}),
                "authority": state.get("authority", {}),
                "evolution_receipts": state.get("evolution_receipts", ()),
                "legacy_unattested_evolution_digests": tuple(
                    state.get("legacy_unattested_evolution_digests", ())
                ),
            }
            if str(state.get("state_digest", "")) != self._state_digest(payload):
                raise ValueError("Goal/Design integrity runtime v2 state digest mismatch")

            base_state = {
                "schema_version": _base.GoalIntegrityRuntime.INTEGRITY_STATE_SCHEMA_VERSION,
                "contracts": payload["contracts"],
                "current_contracts": payload["current_contracts"],
                "authority": payload["authority"],
            }
            temporary = self._validated_base_runtime(base_state)

            receipts = {}
            for row in payload["evolution_receipts"]:
                successor_digest = str(row["successor_digest"])
                if successor_digest in receipts:
                    raise ValueError("duplicate Goal/Design integrity evolution receipt")
                receipt = goal_integrity_evolution_receipt_from_state(row["receipt"])
                successor = temporary._integrity_contracts.get(successor_digest)
                predecessor_digest = temporary._contract_predecessors.get(successor_digest)
                predecessor = temporary._integrity_contracts.get(predecessor_digest)
                if successor is None or predecessor is None:
                    raise ValueError(
                        "Goal/Design evolution receipt references a non-revision contract"
                    )
                verify_goal_integrity_evolution_receipt(
                    receipt,
                    predecessor=predecessor,
                    successor=successor,
                )
                receipts[successor_digest] = receipt

            legacy = {
                str(value)
                for value in payload["legacy_unattested_evolution_digests"]
            }
            revision_digests = {
                digest
                for digest, predecessor in temporary._contract_predecessors.items()
                if predecessor is not None
            }
            if set(receipts) & legacy:
                raise ValueError(
                    "Goal/Design integrity revision cannot be both explicit and legacy-unattested"
                )
            if set(receipts) | legacy != revision_digests:
                raise ValueError(
                    "every Goal/Design integrity revision requires explicit or legacy trust provenance"
                )
        else:
            raise ValueError("unsupported Goal/Design integrity runtime schema")

        # Publish only after base topology, authority, receipt identity and every
        # evolution edge have all been proven on the temporary runtime.
        self._integrity_contracts = dict(temporary._integrity_contracts)
        self._current_contracts = dict(temporary._current_contracts)
        self._contract_predecessors = dict(temporary._contract_predecessors)
        self.integrity_authority = temporary.integrity_authority
        self._evolution_receipts = dict(receipts)
        self._legacy_unattested_evolution_digests = set(legacy)


__all__ = tuple(_base.__all__) + (
    "GoalIntegrityEvolutionReceipt",
    "GoalIntegrityRuntime",
)
