from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.software_engineering import (
    EngineeringEvidenceAttestation,
    EngineeringEvidenceKind,
    EngineeringEvidenceLedger,
)


PROPERTY_EVIDENCE_VERSION = "0.1.0"


def _text(value: Any, *, field: str) -> str:
    result = str(value).strip()
    if not result:
        raise ValueError(f"{field} must be explicit")
    return result


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _refs(values: Sequence[Any]) -> tuple[str, ...]:
    return tuple(sorted({_text(value, field="reference") for value in values}))


class EngineeringClaimClass(str, Enum):
    """The property family that an engineering claim is actually about.

    A claim class is deliberately not inferred from a green command.  It says
    what must be true in the world/repository for the claim to close.
    """

    BUILD_INTEGRITY = "build_integrity"
    FUNCTIONAL_BEHAVIOR = "functional_behavior"
    REGRESSION_PRESERVATION = "regression_preservation"
    DEBUG_ROOT_CAUSE = "debug_root_cause"
    UI_VISUAL_FIDELITY = "ui_visual_fidelity"
    UI_INTERACTION = "ui_interaction"
    UI_ACCESSIBILITY = "ui_accessibility"
    SECURITY_PROPERTY = "security_property"
    PERFORMANCE_PROPERTY = "performance_property"


class EngineeringProofMethod(str, Enum):
    COMPILE = "compile"
    STATIC_ANALYSIS = "static_analysis"
    UNIT_TEST = "unit_test"
    INTEGRATION_TEST = "integration_test"
    PROPERTY_TEST = "property_test"
    METAMORPHIC_TEST = "metamorphic_test"
    REGRESSION_TEST = "regression_test"
    REPRODUCTION = "reproduction"
    CAUSAL_PROBE = "causal_probe"
    BISECT = "bisect"
    VISUAL_DIFF = "visual_diff"
    RESPONSIVE_CHECK = "responsive_check"
    ACCESSIBILITY_AUDIT = "accessibility_audit"
    INTERACTION_E2E = "interaction_e2e"
    SECURITY_TEST = "security_test"
    PERFORMANCE_BENCHMARK = "performance_benchmark"


class EngineeringWitnessRole(str, Enum):
    DIRECT = "direct"
    FALSIFIER = "falsifier"
    REGRESSION = "regression"
    ADVERSARIAL = "adversarial"
    NEGATIVE_CONTROL = "negative_control"


_METHOD_KIND: dict[EngineeringProofMethod, EngineeringEvidenceKind] = {
    EngineeringProofMethod.COMPILE: EngineeringEvidenceKind.COMPILE,
    EngineeringProofMethod.STATIC_ANALYSIS: EngineeringEvidenceKind.STATIC,
    EngineeringProofMethod.UNIT_TEST: EngineeringEvidenceKind.TEST,
    EngineeringProofMethod.INTEGRATION_TEST: EngineeringEvidenceKind.TEST,
    EngineeringProofMethod.PROPERTY_TEST: EngineeringEvidenceKind.TEST,
    EngineeringProofMethod.METAMORPHIC_TEST: EngineeringEvidenceKind.TEST,
    EngineeringProofMethod.REGRESSION_TEST: EngineeringEvidenceKind.TEST,
    EngineeringProofMethod.REPRODUCTION: EngineeringEvidenceKind.REPRODUCTION,
    EngineeringProofMethod.CAUSAL_PROBE: EngineeringEvidenceKind.ROOT_CAUSE,
    EngineeringProofMethod.BISECT: EngineeringEvidenceKind.ROOT_CAUSE,
    EngineeringProofMethod.VISUAL_DIFF: EngineeringEvidenceKind.VISUAL,
    EngineeringProofMethod.RESPONSIVE_CHECK: EngineeringEvidenceKind.RESPONSIVE,
    EngineeringProofMethod.ACCESSIBILITY_AUDIT: EngineeringEvidenceKind.ACCESSIBILITY,
    EngineeringProofMethod.INTERACTION_E2E: EngineeringEvidenceKind.INTERACTION,
    EngineeringProofMethod.SECURITY_TEST: EngineeringEvidenceKind.SECURITY,
    EngineeringProofMethod.PERFORMANCE_BENCHMARK: EngineeringEvidenceKind.PERFORMANCE,
}


@dataclass(frozen=True, slots=True)
class _ClaimPolicy:
    required_method_groups: tuple[tuple[EngineeringProofMethod, ...], ...]
    min_independent_sources: int = 1
    require_version_bound_baseline: bool = False
    require_falsifier: bool = False
    require_adversarial: bool = False


_CLAIM_POLICIES: dict[EngineeringClaimClass, _ClaimPolicy] = {
    EngineeringClaimClass.BUILD_INTEGRITY: _ClaimPolicy(
        required_method_groups=((EngineeringProofMethod.COMPILE,),),
    ),
    EngineeringClaimClass.FUNCTIONAL_BEHAVIOR: _ClaimPolicy(
        required_method_groups=((
            EngineeringProofMethod.INTEGRATION_TEST,
            EngineeringProofMethod.PROPERTY_TEST,
            EngineeringProofMethod.METAMORPHIC_TEST,
            EngineeringProofMethod.UNIT_TEST,
        ),),
    ),
    EngineeringClaimClass.REGRESSION_PRESERVATION: _ClaimPolicy(
        required_method_groups=((EngineeringProofMethod.REGRESSION_TEST,),),
        require_version_bound_baseline=True,
    ),
    EngineeringClaimClass.DEBUG_ROOT_CAUSE: _ClaimPolicy(
        required_method_groups=(
            (EngineeringProofMethod.REPRODUCTION,),
            (EngineeringProofMethod.CAUSAL_PROBE, EngineeringProofMethod.BISECT),
        ),
        require_falsifier=True,
    ),
    EngineeringClaimClass.UI_VISUAL_FIDELITY: _ClaimPolicy(
        required_method_groups=((EngineeringProofMethod.VISUAL_DIFF,),),
    ),
    EngineeringClaimClass.UI_INTERACTION: _ClaimPolicy(
        required_method_groups=((EngineeringProofMethod.INTERACTION_E2E,),),
    ),
    EngineeringClaimClass.UI_ACCESSIBILITY: _ClaimPolicy(
        required_method_groups=((EngineeringProofMethod.ACCESSIBILITY_AUDIT,),),
    ),
    EngineeringClaimClass.SECURITY_PROPERTY: _ClaimPolicy(
        required_method_groups=((EngineeringProofMethod.SECURITY_TEST,),),
        require_adversarial=True,
    ),
    EngineeringClaimClass.PERFORMANCE_PROPERTY: _ClaimPolicy(
        required_method_groups=((EngineeringProofMethod.PERFORMANCE_BENCHMARK,),),
        require_version_bound_baseline=True,
    ),
}


@dataclass(frozen=True, slots=True)
class EngineeringPropertyObligation:
    obligation_id: str
    claim_id: str
    claim_class: EngineeringClaimClass
    property_ref: str
    subject_ref: str
    subject_digest: str
    source_revision: str
    required_method_groups: tuple[tuple[EngineeringProofMethod, ...], ...]
    min_independent_sources: int
    require_version_bound_baseline: bool
    require_falsifier: bool
    require_adversarial: bool
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.obligation_id, "property obligation id"),
            (self.claim_id, "engineering claim id"),
            (self.property_ref, "property ref"),
            (self.subject_ref, "subject ref"),
            (self.subject_digest, "subject digest"),
            (self.source_revision, "source revision"),
            (self.digest, "property obligation digest"),
        ):
            _text(value, field=field)
        if not self.required_method_groups or any(not group for group in self.required_method_groups):
            raise ValueError("property obligation requires proof method groups")
        if self.min_independent_sources < 1:
            raise ValueError("property obligation independent source threshold must be positive")
        if self.authority != "verification_scope_only":
            raise ValueError("property obligation cannot grant mutation/promotion authority")

    def payload(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_class": self.claim_class.value,
            "property_ref": self.property_ref,
            "subject_ref": self.subject_ref,
            "subject_digest": self.subject_digest,
            "source_revision": self.source_revision,
            "required_method_groups": [
                [method.value for method in group] for group in self.required_method_groups
            ],
            "min_independent_sources": self.min_independent_sources,
            "require_version_bound_baseline": self.require_version_bound_baseline,
            "require_falsifier": self.require_falsifier,
            "require_adversarial": self.require_adversarial,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"obligation_id": self.obligation_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPropertyObligation":
        groups = tuple(
            tuple(EngineeringProofMethod(str(method)) for method in group)
            for group in state.get("required_method_groups", ())
        )
        row = cls(
            obligation_id=_text(state["obligation_id"], field="property obligation id"),
            claim_id=_text(state["claim_id"], field="engineering claim id"),
            claim_class=EngineeringClaimClass(str(state["claim_class"])),
            property_ref=_text(state["property_ref"], field="property ref"),
            subject_ref=_text(state["subject_ref"], field="subject ref"),
            subject_digest=_text(state["subject_digest"], field="subject digest"),
            source_revision=_text(state["source_revision"], field="source revision"),
            required_method_groups=groups,
            min_independent_sources=int(state["min_independent_sources"]),
            require_version_bound_baseline=bool(state["require_version_bound_baseline"]),
            require_falsifier=bool(state["require_falsifier"]),
            require_adversarial=bool(state["require_adversarial"]),
            authority=_text(state["authority"], field="property obligation authority"),
            digest=_text(state["digest"], field="property obligation digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.obligation_id != f"eng-property-obligation-{expected[:20]}":
            raise ValueError("property obligation digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringPropertyWitness:
    witness_id: str
    obligation_id: str
    obligation_digest: str
    attestation_id: str
    attestation_digest: str
    method: EngineeringProofMethod
    role: EngineeringWitnessRole
    measured_property_ref: str
    oracle_ref: str
    source_family: str
    baseline_revision: str | None
    falsifier_ref: str | None
    adversarial: bool
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.witness_id, "property witness id"),
            (self.obligation_id, "property obligation id"),
            (self.obligation_digest, "property obligation digest"),
            (self.attestation_id, "engineering attestation id"),
            (self.attestation_digest, "engineering attestation digest"),
            (self.measured_property_ref, "measured property ref"),
            (self.oracle_ref, "oracle ref"),
            (self.source_family, "source family"),
            (self.digest, "property witness digest"),
        ):
            _text(value, field=field)
        if self.authority != "evidence_scope_only":
            raise ValueError("property witness cannot grant mutation/promotion authority")

    def payload(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "obligation_digest": self.obligation_digest,
            "attestation_id": self.attestation_id,
            "attestation_digest": self.attestation_digest,
            "method": self.method.value,
            "role": self.role.value,
            "measured_property_ref": self.measured_property_ref,
            "oracle_ref": self.oracle_ref,
            "source_family": self.source_family,
            "baseline_revision": self.baseline_revision,
            "falsifier_ref": self.falsifier_ref,
            "adversarial": self.adversarial,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"witness_id": self.witness_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPropertyWitness":
        row = cls(
            witness_id=_text(state["witness_id"], field="property witness id"),
            obligation_id=_text(state["obligation_id"], field="property obligation id"),
            obligation_digest=_text(state["obligation_digest"], field="property obligation digest"),
            attestation_id=_text(state["attestation_id"], field="engineering attestation id"),
            attestation_digest=_text(state["attestation_digest"], field="engineering attestation digest"),
            method=EngineeringProofMethod(str(state["method"])),
            role=EngineeringWitnessRole(str(state["role"])),
            measured_property_ref=_text(state["measured_property_ref"], field="measured property ref"),
            oracle_ref=_text(state["oracle_ref"], field="oracle ref"),
            source_family=_text(state["source_family"], field="source family"),
            baseline_revision=_optional_text(state.get("baseline_revision")),
            falsifier_ref=_optional_text(state.get("falsifier_ref")),
            adversarial=bool(state.get("adversarial", False)),
            authority=_text(state["authority"], field="property witness authority"),
            digest=_text(state["digest"], field="property witness digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.witness_id != f"eng-property-witness-{expected[:20]}":
            raise ValueError("property witness digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringPropertyClosureReceipt:
    receipt_id: str
    obligation_id: str
    obligation_digest: str
    witness_ids: tuple[str, ...]
    witness_digests: tuple[tuple[str, str], ...]
    ready: bool
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        if self.authority != "candidate_only":
            raise ValueError("property closure cannot hold promotion authority")
        if self.ready and self.reasons:
            raise ValueError("ready property closure cannot contain blocking reasons")
        if len(self.witness_ids) != len(set(self.witness_ids)):
            raise ValueError("property closure cannot contain duplicate witnesses")

    def payload(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "obligation_digest": self.obligation_digest,
            "witness_ids": list(self.witness_ids),
            "witness_digests": [list(row) for row in self.witness_digests],
            "ready": self.ready,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringPropertyClosureReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="property closure receipt id"),
            obligation_id=_text(state["obligation_id"], field="property obligation id"),
            obligation_digest=_text(state["obligation_digest"], field="property obligation digest"),
            witness_ids=_refs(tuple(state.get("witness_ids", ()))),
            witness_digests=tuple(
                (_text(value[0], field="witness id"), _text(value[1], field="witness digest"))
                for value in state.get("witness_digests", ())
            ),
            ready=bool(state["ready"]),
            reasons=tuple(str(value) for value in state.get("reasons", ())),
            authority=_text(state["authority"], field="property closure authority"),
            digest=_text(state["digest"], field="property closure digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-property-closure-{expected[:20]}":
            raise ValueError("property closure receipt digest/id mismatch")
        return row


class EngineeringPropertyEvidenceLedger:
    """Claim-specific proof obligations over canonical engineering attestations.

    The base EngineeringEvidenceLedger answers whether an attestation is fresh,
    independent-authority evidence for a particular patch revision.  This layer
    answers the different question: does that evidence actually measure the
    property being claimed with an adequate proof method?

    The layer is intentionally non-mutating.  Obligations and witnesses hold
    verification/evidence scope only; closure receipts are candidate-only.
    """

    def __init__(self, *, evidence: EngineeringEvidenceLedger) -> None:
        self.evidence = evidence
        self._obligations: dict[str, EngineeringPropertyObligation] = {}
        self._witnesses: dict[str, EngineeringPropertyWitness] = {}
        self._receipts: dict[str, EngineeringPropertyClosureReceipt] = {}

    def obligations(self) -> tuple[EngineeringPropertyObligation, ...]:
        return tuple(self._obligations[key] for key in sorted(self._obligations))

    def witnesses(self) -> tuple[EngineeringPropertyWitness, ...]:
        return tuple(self._witnesses[key] for key in sorted(self._witnesses))

    def receipts(self) -> tuple[EngineeringPropertyClosureReceipt, ...]:
        return tuple(self._receipts[key] for key in sorted(self._receipts))

    def get_obligation(self, obligation_id: str) -> EngineeringPropertyObligation:
        try:
            return self._obligations[str(obligation_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering property obligation: {obligation_id}") from exc

    def get_witness(self, witness_id: str) -> EngineeringPropertyWitness:
        try:
            return self._witnesses[str(witness_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering property witness: {witness_id}") from exc

    def get_receipt(self, receipt_id: str) -> EngineeringPropertyClosureReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering property closure: {receipt_id}") from exc

    def register_obligation(
        self,
        *,
        claim_id: str,
        claim_class: EngineeringClaimClass,
        property_ref: str,
        subject_ref: str,
        subject_digest: str,
        source_revision: str,
        min_independent_sources: int | None = None,
    ) -> EngineeringPropertyObligation:
        claim_kind = EngineeringClaimClass(claim_class)
        policy = _CLAIM_POLICIES[claim_kind]
        threshold = policy.min_independent_sources if min_independent_sources is None else int(min_independent_sources)
        if threshold < 1:
            raise ValueError("property obligation independent source threshold must be positive")
        payload = {
            "claim_id": _text(claim_id, field="engineering claim id"),
            "claim_class": claim_kind.value,
            "property_ref": _text(property_ref, field="property ref"),
            "subject_ref": _text(subject_ref, field="subject ref"),
            "subject_digest": _text(subject_digest, field="subject digest"),
            "source_revision": _text(source_revision, field="source revision"),
            "required_method_groups": [
                [method.value for method in group] for group in policy.required_method_groups
            ],
            "min_independent_sources": threshold,
            "require_version_bound_baseline": policy.require_version_bound_baseline,
            "require_falsifier": policy.require_falsifier,
            "require_adversarial": policy.require_adversarial,
            "authority": "verification_scope_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringPropertyObligation(
            obligation_id=f"eng-property-obligation-{digest[:20]}",
            claim_id=payload["claim_id"],
            claim_class=claim_kind,
            property_ref=payload["property_ref"],
            subject_ref=payload["subject_ref"],
            subject_digest=payload["subject_digest"],
            source_revision=payload["source_revision"],
            required_method_groups=policy.required_method_groups,
            min_independent_sources=threshold,
            require_version_bound_baseline=policy.require_version_bound_baseline,
            require_falsifier=policy.require_falsifier,
            require_adversarial=policy.require_adversarial,
            authority="verification_scope_only",
            digest=digest,
        )
        existing = self._obligations.get(row.obligation_id)
        if existing is not None and existing != row:
            raise ValueError("property obligation id cannot be rebound")
        self._obligations[row.obligation_id] = row
        return existing or row

    @staticmethod
    def _method_matches_attestation(
        method: EngineeringProofMethod,
        attestation: EngineeringEvidenceAttestation,
    ) -> bool:
        return _METHOD_KIND[EngineeringProofMethod(method)] is attestation.kind

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
        obligation = self.get_obligation(obligation_id)
        attestation = self.evidence.get(attestation_id)
        proof_method = EngineeringProofMethod(method)
        if not self._method_matches_attestation(proof_method, attestation):
            raise ValueError(
                f"proof method {proof_method.value} is incompatible with attestation kind {attestation.kind.value}"
            )
        payload = {
            "obligation_id": obligation.obligation_id,
            "obligation_digest": obligation.digest,
            "attestation_id": attestation.attestation_id,
            "attestation_digest": attestation.digest,
            "method": proof_method.value,
            "role": EngineeringWitnessRole(role).value,
            "measured_property_ref": _text(measured_property_ref, field="measured property ref"),
            "oracle_ref": _text(oracle_ref, field="oracle ref"),
            "source_family": _text(source_family, field="source family"),
            "baseline_revision": _optional_text(baseline_revision),
            "falsifier_ref": _optional_text(falsifier_ref),
            "adversarial": bool(adversarial),
            "authority": "evidence_scope_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringPropertyWitness(
            witness_id=f"eng-property-witness-{digest[:20]}",
            obligation_id=obligation.obligation_id,
            obligation_digest=obligation.digest,
            attestation_id=attestation.attestation_id,
            attestation_digest=attestation.digest,
            method=proof_method,
            role=EngineeringWitnessRole(payload["role"]),
            measured_property_ref=payload["measured_property_ref"],
            oracle_ref=payload["oracle_ref"],
            source_family=payload["source_family"],
            baseline_revision=payload["baseline_revision"],
            falsifier_ref=payload["falsifier_ref"],
            adversarial=payload["adversarial"],
            authority="evidence_scope_only",
            digest=digest,
        )
        existing = self._witnesses.get(row.witness_id)
        if existing is not None and existing != row:
            raise ValueError("property witness id cannot be rebound")
        self._witnesses[row.witness_id] = row
        return existing or row

    def assess(
        self,
        obligation_id: str,
        *,
        witness_ids: tuple[str, ...],
    ) -> EngineeringPropertyClosureReceipt:
        obligation = self.get_obligation(obligation_id)
        identities = _refs(witness_ids)
        reasons: list[str] = []
        if not identities:
            reasons.append("missing_property_witness")

        valid: list[EngineeringPropertyWitness] = []
        for identity in identities:
            witness = self.get_witness(identity)
            if witness.obligation_id != obligation.obligation_id or witness.obligation_digest != obligation.digest:
                reasons.append(f"witness_obligation_mismatch:{witness.witness_id}")
                continue
            try:
                attestation = self.evidence.get(witness.attestation_id)
            except KeyError:
                reasons.append(f"unknown_attestation:{witness.attestation_id}")
                continue
            if attestation.digest != witness.attestation_digest:
                reasons.append(f"attestation_identity_mismatch:{witness.attestation_id}")
                continue
            if not self._method_matches_attestation(witness.method, attestation):
                reasons.append(f"method_attestation_kind_mismatch:{witness.witness_id}")
                continue
            if attestation.subject_ref != obligation.subject_ref or attestation.subject_digest != obligation.subject_digest:
                reasons.append(f"witness_subject_mismatch:{witness.witness_id}")
                continue
            if attestation.source_revision != obligation.source_revision:
                reasons.append(f"witness_source_revision_mismatch:{witness.witness_id}")
                continue
            if not self.evidence.is_valid(
                attestation.attestation_id,
                subject_ref=obligation.subject_ref,
                subject_digest=obligation.subject_digest,
                source_revision=obligation.source_revision,
            ):
                reasons.append(f"revoked_or_invalid_attestation:{attestation.attestation_id}")
                continue
            if witness.measured_property_ref != obligation.property_ref:
                reasons.append(f"proxy_measurement:{witness.witness_id}")
                continue
            valid.append(witness)

        methods = {witness.method for witness in valid}
        for group in obligation.required_method_groups:
            if not any(method in methods for method in group):
                reasons.append(
                    "missing_required_method_group:" + "|".join(method.value for method in group)
                )

        if obligation.require_version_bound_baseline and not any(
            witness.baseline_revision for witness in valid
        ):
            reasons.append("missing_version_bound_baseline")
        if obligation.require_falsifier and not any(
            witness.role is EngineeringWitnessRole.FALSIFIER and witness.falsifier_ref
            for witness in valid
        ):
            reasons.append("missing_falsifier_witness")
        if obligation.require_adversarial and not any(
            witness.adversarial or witness.role is EngineeringWitnessRole.ADVERSARIAL
            for witness in valid
        ):
            reasons.append("missing_adversarial_witness")

        source_families = {witness.source_family for witness in valid}
        if len(source_families) < obligation.min_independent_sources:
            reasons.append(
                "independent_source_families_below_threshold:"
                f"{len(source_families)}<{obligation.min_independent_sources}"
            )

        normalized = tuple(sorted(set(reasons)))
        ready = not normalized
        witness_digests = tuple(
            (identity, self.get_witness(identity).digest) for identity in identities
        )
        payload = {
            "obligation_id": obligation.obligation_id,
            "obligation_digest": obligation.digest,
            "witness_ids": list(identities),
            "witness_digests": [list(row) for row in witness_digests],
            "ready": ready,
            "reasons": list(normalized),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringPropertyClosureReceipt(
            receipt_id=f"eng-property-closure-{digest[:20]}",
            obligation_id=obligation.obligation_id,
            obligation_digest=obligation.digest,
            witness_ids=identities,
            witness_digests=witness_digests,
            ready=ready,
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
        return {
            "version": PROPERTY_EVIDENCE_VERSION,
            "obligations": [row.to_state() for row in self.obligations()],
            "witnesses": [row.to_state() for row in self.witnesses()],
            "receipts": [row.to_state() for row in self.receipts()],
        }

    @classmethod
    def from_state(
        cls,
        *,
        evidence: EngineeringEvidenceLedger,
        state: Mapping[str, Any],
    ) -> "EngineeringPropertyEvidenceLedger":
        version = str(state.get("version", PROPERTY_EVIDENCE_VERSION))
        if version != PROPERTY_EVIDENCE_VERSION:
            raise ValueError("unsupported engineering property evidence snapshot version")
        ledger = cls(evidence=evidence)
        for value in state.get("obligations", ()):
            row = EngineeringPropertyObligation.from_state(value)
            existing = ledger._obligations.get(row.obligation_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound property obligation")
            ledger._obligations[row.obligation_id] = row
        for value in state.get("witnesses", ()):
            row = EngineeringPropertyWitness.from_state(value)
            obligation = ledger.get_obligation(row.obligation_id)
            if row.obligation_digest != obligation.digest:
                raise ValueError("property witness obligation digest mismatch")
            attestation = evidence.get(row.attestation_id)
            if attestation.digest != row.attestation_digest:
                raise ValueError("property witness attestation digest mismatch")
            if not ledger._method_matches_attestation(row.method, attestation):
                raise ValueError("property witness method/attestation kind mismatch")
            existing = ledger._witnesses.get(row.witness_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound property witness")
            ledger._witnesses[row.witness_id] = row
        for value in state.get("receipts", ()):
            row = EngineeringPropertyClosureReceipt.from_state(value)
            obligation = ledger.get_obligation(row.obligation_id)
            if row.obligation_digest != obligation.digest:
                raise ValueError("property closure obligation digest mismatch")
            expected_witness_digests = tuple(
                (identity, ledger.get_witness(identity).digest) for identity in row.witness_ids
            )
            if row.witness_digests != expected_witness_digests:
                raise ValueError("property closure witness lineage mismatch")
            existing = ledger._receipts.get(row.receipt_id)
            if existing is not None and existing != row:
                raise ValueError("duplicate/rebound property closure receipt")
            ledger._receipts[row.receipt_id] = row
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
