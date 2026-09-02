from __future__ import annotations

from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core._software_engineering_property_evidence_v01 import (
    PROPERTY_EVIDENCE_VERSION as _FROZEN_PROPERTY_EVIDENCE_VERSION,
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringPropertyClosureReceipt,
    EngineeringPropertyEvidenceLedger as _EngineeringPropertyEvidenceLedgerV01,
    EngineeringPropertyObligation,
    EngineeringPropertyWitness,
    EngineeringWitnessRole,
)


PROPERTY_EVIDENCE_VERSION = "0.3.0"

# These methods share one coarse canonical EngineeringEvidenceKind with other
# proof methods. Their semantic identity therefore cannot be recovered from the
# kind alone and must be explicitly bound by immutable verifier evidence.
_AMBIGUOUS_PROOF_METHODS = frozenset(
    {
        EngineeringProofMethod.UNIT_TEST,
        EngineeringProofMethod.INTEGRATION_TEST,
        EngineeringProofMethod.PROPERTY_TEST,
        EngineeringProofMethod.METAMORPHIC_TEST,
        EngineeringProofMethod.REGRESSION_TEST,
        EngineeringProofMethod.CAUSAL_PROBE,
        EngineeringProofMethod.BISECT,
    }
)


class EngineeringPropertyEvidenceLedger(_EngineeringPropertyEvidenceLedgerV01):
    """Property evidence with verifier-grounded semantic and lineage authority.

    F v1.3 hardened independent-source lineage. F v1.4 closes the remaining
    semantic laundering boundary without changing the frozen v0.2 witness
    schema: caller-owned ``method``, ``baseline_revision``, ``falsifier_ref``
    and policy-significant witness-role/adversarial fields only carry current
    semantic authority when the immutable verifier attestation binds the exact
    marker.

    The frozen v0.2 state schema remains audit-restorable. New ledgers serialize
    as v0.3. A restored v0.2 ledger preserves its historical serialization
    version until a new assessment/witness is produced, so containing control
    snapshots can still round-trip byte-for-byte when no new current claim is
    minted. Historical ready receipts that relied on ungrounded semantics fail
    closed during restore instead of being upgraded by compatibility logic.
    """

    def __init__(self, *, evidence: Any) -> None:
        super().__init__(evidence=evidence)
        self._serialization_version = PROPERTY_EVIDENCE_VERSION

    @staticmethod
    def _attested_refs(attestation: Any) -> frozenset[str]:
        return frozenset(str(value) for value in attestation.evidence_refs)

    @classmethod
    def _semantic_grounding_reasons_for_values(
        cls,
        *,
        method: EngineeringProofMethod,
        role: EngineeringWitnessRole,
        baseline_revision: str | None,
        falsifier_ref: str | None,
        adversarial: bool,
        attestation: Any,
        witness_id: str,
    ) -> tuple[str, ...]:
        refs = cls._attested_refs(attestation)
        reasons: list[str] = []

        proof_method = EngineeringProofMethod(method)
        method_marker = f"proof-method:{proof_method.value}"
        declared_method_markers = {
            ref for ref in refs if ref.startswith("proof-method:")
        }
        if (
            proof_method in _AMBIGUOUS_PROOF_METHODS
            or declared_method_markers
        ) and method_marker not in refs:
            reasons.append(f"proof_method_not_attested:{witness_id}")

        witness_role = EngineeringWitnessRole(role)
        if witness_role is not EngineeringWitnessRole.DIRECT:
            role_marker = f"witness-role:{witness_role.value}"
            if role_marker not in refs:
                reasons.append(f"witness_role_not_attested:{witness_id}")

        if baseline_revision is not None:
            baseline_marker = f"baseline-revision:{baseline_revision}"
            if baseline_marker not in refs:
                reasons.append(f"baseline_revision_not_attested:{witness_id}")

        if falsifier_ref is not None:
            falsifier_marker = f"falsifier-ref:{falsifier_ref}"
            if falsifier_marker not in refs:
                reasons.append(f"falsifier_ref_not_attested:{witness_id}")

        if adversarial and "adversarial:true" not in refs:
            reasons.append(f"adversarial_not_attested:{witness_id}")

        return tuple(sorted(set(reasons)))

    @classmethod
    def _witness_semantic_grounding_reasons(
        cls,
        witness: EngineeringPropertyWitness,
        attestation: Any,
    ) -> tuple[str, ...]:
        return cls._semantic_grounding_reasons_for_values(
            method=witness.method,
            role=witness.role,
            baseline_revision=witness.baseline_revision,
            falsifier_ref=witness.falsifier_ref,
            adversarial=witness.adversarial,
            attestation=attestation,
            witness_id=witness.witness_id,
        )

    @classmethod
    def _assert_semantic_grounding(
        cls,
        *,
        method: EngineeringProofMethod,
        role: EngineeringWitnessRole,
        baseline_revision: str | None,
        falsifier_ref: str | None,
        adversarial: bool,
        attestation: Any,
    ) -> None:
        refs = cls._attested_refs(attestation)
        proof_method = EngineeringProofMethod(method)
        method_marker = f"proof-method:{proof_method.value}"
        declared_method_markers = {
            ref for ref in refs if ref.startswith("proof-method:")
        }
        if (
            proof_method in _AMBIGUOUS_PROOF_METHODS
            or declared_method_markers
        ) and method_marker not in refs:
            raise ValueError(
                f"proof method {proof_method.value} is not verifier-attested by {method_marker}"
            )

        witness_role = EngineeringWitnessRole(role)
        if witness_role is not EngineeringWitnessRole.DIRECT:
            role_marker = f"witness-role:{witness_role.value}"
            if role_marker not in refs:
                raise ValueError(
                    f"witness role {witness_role.value} is not verifier-attested by {role_marker}"
                )

        if baseline_revision is not None:
            baseline_marker = f"baseline-revision:{baseline_revision}"
            if baseline_marker not in refs:
                raise ValueError(
                    f"baseline revision {baseline_revision} is not verifier-attested by {baseline_marker}"
                )

        if falsifier_ref is not None:
            falsifier_marker = f"falsifier-ref:{falsifier_ref}"
            if falsifier_marker not in refs:
                raise ValueError(
                    f"falsifier reference {falsifier_ref} is not verifier-attested by {falsifier_marker}"
                )

        if adversarial and "adversarial:true" not in refs:
            raise ValueError(
                "adversarial witness semantics are not verifier-attested by adversarial:true"
            )

    def record_witness(
        self,
        *,
        obligation_id: str,
        attestation_id: str,
        method: EngineeringProofMethod,
        role: EngineeringWitnessRole,
        measured_property_ref: str,
        oracle_ref: str,
        source_family: str,
        baseline_revision: str | None = None,
        falsifier_ref: str | None = None,
        adversarial: bool = False,
    ) -> EngineeringPropertyWitness:
        attestation = self.evidence.get(attestation_id)
        proof_method = EngineeringProofMethod(method)
        witness_role = EngineeringWitnessRole(role)
        self._assert_semantic_grounding(
            method=proof_method,
            role=witness_role,
            baseline_revision=baseline_revision,
            falsifier_ref=falsifier_ref,
            adversarial=bool(adversarial),
            attestation=attestation,
        )
        row = super().record_witness(
            obligation_id=obligation_id,
            attestation_id=attestation_id,
            method=proof_method,
            role=witness_role,
            measured_property_ref=measured_property_ref,
            oracle_ref=oracle_ref,
            source_family=source_family,
            baseline_revision=baseline_revision,
            falsifier_ref=falsifier_ref,
            adversarial=adversarial,
        )
        self._serialization_version = PROPERTY_EVIDENCE_VERSION
        return row

    def _baseline_valid_family_rows(
        self,
        obligation: EngineeringPropertyObligation,
        witness_ids: tuple[str, ...],
    ) -> list[tuple[EngineeringPropertyWitness, Any]]:
        rows: list[tuple[EngineeringPropertyWitness, Any]] = []
        for identity in witness_ids:
            try:
                witness = self.get_witness(identity)
                attestation = self.evidence.get(witness.attestation_id)
            except KeyError:
                continue
            if (
                witness.obligation_id != obligation.obligation_id
                or witness.obligation_digest != obligation.digest
                or attestation.digest != witness.attestation_digest
                or not self._method_matches_attestation(witness.method, attestation)
                or attestation.subject_ref != obligation.subject_ref
                or attestation.subject_digest != obligation.subject_digest
                or attestation.source_revision != obligation.source_revision
                or not self.evidence.is_valid(
                    attestation.attestation_id,
                    subject_ref=obligation.subject_ref,
                    subject_digest=obligation.subject_digest,
                    source_revision=obligation.source_revision,
                )
                or witness.measured_property_ref != obligation.property_ref
                or not self._oracle_is_attested(witness.oracle_ref, attestation)
                or self._witness_semantic_grounding_reasons(witness, attestation)
            ):
                continue
            rows.append((witness, attestation))
        return rows

    @staticmethod
    def _family_is_explicitly_attested(witness: EngineeringPropertyWitness, attestation: Any) -> bool:
        return witness.source_family in set(attestation.evidence_refs)

    def _independence_grounding_reasons(
        self,
        obligation: EngineeringPropertyObligation,
        witness_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        if obligation.min_independent_sources <= 1:
            return ()

        rows = self._baseline_valid_family_rows(obligation, witness_ids)
        families = {witness.source_family for witness, _ in rows}
        if len(families) < obligation.min_independent_sources:
            # The base policy already blocks insufficient family count; no
            # additional provenance claim is needed to explain that failure.
            return ()

        by_family: dict[str, list[tuple[EngineeringPropertyWitness, Any]]] = {}
        for witness, attestation in rows:
            by_family.setdefault(witness.source_family, []).append((witness, attestation))

        explicitly_attested = {
            family
            for family, family_rows in by_family.items()
            if all(
                self._family_is_explicitly_attested(witness, attestation)
                for witness, attestation in family_rows
            )
        }

        verifier_owners: dict[str, set[str]] = {}
        environment_owners: dict[str, set[str]] = {}
        for family, family_rows in by_family.items():
            for _, attestation in family_rows:
                verifier_owners.setdefault(attestation.verifier_agent_id, set()).add(family)
                environment_owners.setdefault(attestation.environment_digest, set()).add(family)

        reasons: list[str] = []
        for family, family_rows in by_family.items():
            if family in explicitly_attested:
                continue
            family_is_verifier_grounded = all(
                len(verifier_owners[attestation.verifier_agent_id]) == 1
                and len(environment_owners[attestation.environment_digest]) == 1
                for _, attestation in family_rows
            )
            if family_is_verifier_grounded:
                continue
            reasons.extend(
                f"source_family_not_attested:{witness.witness_id}"
                for witness, _ in family_rows
            )
        return tuple(sorted(set(reasons)))

    def _semantic_grounding_reasons(
        self,
        witness_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        for identity in witness_ids:
            try:
                witness = self.get_witness(identity)
                attestation = self.evidence.get(witness.attestation_id)
            except KeyError:
                continue
            reasons.extend(
                self._witness_semantic_grounding_reasons(witness, attestation)
            )
        return tuple(sorted(set(reasons)))

    def assess(
        self,
        obligation_id: str,
        *,
        witness_ids: tuple[str, ...],
    ) -> EngineeringPropertyClosureReceipt:
        self._serialization_version = PROPERTY_EVIDENCE_VERSION
        previous_receipt_ids = set(self._receipts)
        base = super().assess(obligation_id, witness_ids=witness_ids)
        obligation = self.get_obligation(obligation_id)
        semantic = self._semantic_grounding_reasons(base.witness_ids)
        independence = self._independence_grounding_reasons(
            obligation,
            base.witness_ids,
        )
        extra = tuple(sorted(set(semantic).union(independence)))
        if not extra:
            return base

        # Do not persist a freshly computed optimistic base receipt when this
        # v0.3 layer immediately proves that its semantic authority is invalid.
        # Historical receipts that existed before this assessment remain audit
        # facts and are never deleted.
        if base.receipt_id not in previous_receipt_ids:
            self._receipts.pop(base.receipt_id, None)

        normalized = tuple(sorted(set(base.reasons).union(extra)))
        payload = {
            "obligation_id": base.obligation_id,
            "obligation_digest": base.obligation_digest,
            "witness_ids": list(base.witness_ids),
            "witness_digests": [list(row) for row in base.witness_digests],
            "ready": False,
            "reasons": list(normalized),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringPropertyClosureReceipt(
            receipt_id=f"eng-property-closure-{digest[:20]}",
            obligation_id=base.obligation_id,
            obligation_digest=base.obligation_digest,
            witness_ids=base.witness_ids,
            witness_digests=base.witness_digests,
            ready=False,
            reasons=normalized,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("property closure receipt id cannot be rebound")
        self._receipts[row.receipt_id] = row
        return existing or row

    def to_state(self) -> dict[str, Any]:
        state = super().to_state()
        state["version"] = self._serialization_version
        return state

    @classmethod
    def from_state(
        cls,
        *,
        evidence: Any,
        state: Mapping[str, Any],
    ) -> "EngineeringPropertyEvidenceLedger":
        version = str(state.get("version", _FROZEN_PROPERTY_EVIDENCE_VERSION))
        if version not in {
            _FROZEN_PROPERTY_EVIDENCE_VERSION,
            PROPERTY_EVIDENCE_VERSION,
        }:
            raise ValueError("unsupported engineering property evidence snapshot version")

        # The frozen implementation owns the exact v0.2 shape/digest checks.
        # Normalize only the outer protocol tag for that immutable parser; no
        # witness, receipt or attestation content is rewritten or augmented.
        frozen_state = dict(state)
        frozen_state["version"] = _FROZEN_PROPERTY_EVIDENCE_VERSION
        ledger = super().from_state(evidence=evidence, state=frozen_state)
        ledger._serialization_version = version

        # v0.3 states may never contain a witness that could not have been
        # admitted through the v0.3 record_witness boundary.
        if version == PROPERTY_EVIDENCE_VERSION:
            for witness in ledger.witnesses():
                attestation = evidence.get(witness.attestation_id)
                if ledger._witness_semantic_grounding_reasons(witness, attestation):
                    raise ValueError(
                        "v0.3 property witness contains ungrounded semantic verifier claims"
                    )

        # v0.2 remains an audit-compatible historical format, but historical
        # ready=True cannot be imported as current semantic authority when its
        # method/baseline/falsifier/role/adversarial claims are not verifier
        # grounded. The same rule retains the F v1.3 independence hardening.
        for receipt in ledger.receipts():
            if not receipt.ready:
                continue
            obligation = ledger.get_obligation(receipt.obligation_id)
            semantic = ledger._semantic_grounding_reasons(receipt.witness_ids)
            independence = ledger._independence_grounding_reasons(
                obligation,
                receipt.witness_ids,
            )
            if semantic:
                raise ValueError(
                    "ready property closure contains ungrounded semantic verifier claims"
                )
            if independence:
                raise ValueError(
                    "ready property closure contains ungrounded independent source families"
                )
        return ledger


__all__ = (
    "PROPERTY_EVIDENCE_VERSION",
    "EngineeringClaimClass",
    "EngineeringProofMethod",
    "EngineeringWitnessRole",
    "EngineeringPropertyObligation",
    "EngineeringPropertyWitness",
    "EngineeringPropertyClosureReceipt",
    "EngineeringPropertyEvidenceLedger",
)
