from __future__ import annotations

from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core._software_engineering_property_evidence_v01 import (
    PROPERTY_EVIDENCE_VERSION,
    EngineeringClaimClass,
    EngineeringProofMethod,
    EngineeringPropertyClosureReceipt,
    EngineeringPropertyEvidenceLedger as _EngineeringPropertyEvidenceLedgerV01,
    EngineeringPropertyObligation,
    EngineeringPropertyWitness,
    EngineeringWitnessRole,
)


class EngineeringPropertyEvidenceLedger(_EngineeringPropertyEvidenceLedgerV01):
    """Property evidence with verifier-grounded independence lineage.

    A caller-owned source-family label may collapse witnesses into one lineage,
    but it cannot by itself manufacture multiple independent lineages. When an
    obligation requires more than one independent source, distinct family
    labels must either be explicitly present in immutable verifier evidence
    refs or be backed by non-shared verifier identities and environment digests.
    """

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

    def assess(
        self,
        obligation_id: str,
        *,
        witness_ids: tuple[str, ...],
    ) -> EngineeringPropertyClosureReceipt:
        base = super().assess(obligation_id, witness_ids=witness_ids)
        obligation = self.get_obligation(obligation_id)
        extra = self._independence_grounding_reasons(obligation, base.witness_ids)
        if not extra:
            return base

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

    @classmethod
    def from_state(
        cls,
        *,
        evidence: Any,
        state: Mapping[str, Any],
    ) -> "EngineeringPropertyEvidenceLedger":
        ledger = super().from_state(evidence=evidence, state=state)
        for receipt in ledger.receipts():
            if not receipt.ready:
                continue
            obligation = ledger.get_obligation(receipt.obligation_id)
            reasons = ledger._independence_grounding_reasons(
                obligation,
                receipt.witness_ids,
            )
            if reasons:
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
