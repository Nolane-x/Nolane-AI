from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest


OBSERVATION_SURFACE_PROTOCOL = "external-canonical-observation-surface-v1"
SURFACE_RECEIPT_PROTOCOL = "external-surface-observation-receipt-v1"
OBSERVATION_PROTOCOL = "external-canonical-observation-v1"

REQUIRED_SURFACE_KINDS = (
    "artifact",
    "authority-graph",
    "evidence",
    "freshness",
    "handoff",
    "registry",
    "source-state",
    "work-trace",
)


def _exact_keys(state: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if any(type(key) is not str for key in state):
        raise ValueError(f"{label} state keys must be exact strings")
    actual = frozenset(state)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unknown:
            details.append("unknown=" + ",".join(unknown))
        raise ValueError(f"{label} state is non-canonical: " + ";".join(details))


def _exact_non_empty_string(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be an exact non-empty string")
    return value


def _exact_epoch(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError("observed epoch must be an exact non-negative integer")
    return value


def _exact_string_sequence(value: object, label: str) -> tuple[str, ...]:
    if type(value) is not list:
        raise ValueError(f"{label} must be a serialized list")
    rows: list[str] = []
    for row in value:
        rows.append(_exact_non_empty_string(row, label))
    return tuple(rows)


def _validated_component_ids(values: Sequence[str]) -> tuple[str, ...]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        component_id = _exact_non_empty_string(value, "required component identity")
        if component_id in seen:
            raise ValueError(f"duplicate required component identity: {component_id}")
        seen.add(component_id)
        rows.append(component_id)
    return tuple(sorted(rows))


@dataclass(frozen=True, slots=True)
class ObservationFinding:
    code: str
    detail: str
    subject_id: str

    def to_state(self) -> dict[str, str]:
        return {
            "code": self.code,
            "detail": self.detail,
            "subject_id": self.subject_id,
        }


@dataclass(frozen=True, slots=True)
class CanonicalObservationSurfaceContract:
    protocol: str
    required_component_ids: tuple[str, ...]
    required_surface_kinds: tuple[str, ...]
    digest: str

    @classmethod
    def create(
        cls,
        *,
        required_component_ids: Sequence[str],
    ) -> "CanonicalObservationSurfaceContract":
        component_ids = _validated_component_ids(required_component_ids)
        payload = {
            "protocol": OBSERVATION_SURFACE_PROTOCOL,
            "required_component_ids": list(component_ids),
            "required_surface_kinds": list(REQUIRED_SURFACE_KINDS),
        }
        return cls(
            protocol=OBSERVATION_SURFACE_PROTOCOL,
            required_component_ids=component_ids,
            required_surface_kinds=REQUIRED_SURFACE_KINDS,
            digest="observation-surface-v1-" + canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "required_component_ids": list(self.required_component_ids),
            "required_surface_kinds": list(self.required_surface_kinds),
            "digest": self.digest,
        }

    @classmethod
    def from_state(
        cls,
        state: Mapping[str, Any],
    ) -> "CanonicalObservationSurfaceContract":
        if not isinstance(state, Mapping):
            raise ValueError("canonical observation surface contract state must be an object")
        _exact_keys(
            state,
            frozenset(
                {
                    "protocol",
                    "required_component_ids",
                    "required_surface_kinds",
                    "digest",
                }
            ),
            "canonical observation surface contract",
        )
        if state.get("protocol") != OBSERVATION_SURFACE_PROTOCOL:
            raise ValueError("canonical observation surface contract protocol mismatch")
        component_ids = _exact_string_sequence(
            state.get("required_component_ids"),
            "required component identities",
        )
        surface_kinds = _exact_string_sequence(
            state.get("required_surface_kinds"),
            "required surface kinds",
        )
        if surface_kinds != REQUIRED_SURFACE_KINDS:
            raise ValueError("canonical observation required surface kinds mismatch")
        expected = cls.create(required_component_ids=component_ids)
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError(
                "canonical observation surface contract state is non-canonical or digest-mismatched"
            )
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("canonical observation surface contract integrity validation failed") from exc
        if restored != self:
            raise ValueError("canonical observation surface contract integrity validation failed")


@dataclass(frozen=True, slots=True)
class SurfaceObservationReceipt:
    protocol: str
    surface_kind: str
    provider_id: str
    provider_version: str
    source_locator: str
    scope_digest: str
    observed_state_digest: str
    enumeration_complete: bool
    observed_epoch: int
    digest: str

    @classmethod
    def create(
        cls,
        *,
        surface_kind: str,
        provider_id: str,
        provider_version: str,
        source_locator: str,
        scope_digest: str,
        observed_state_digest: str,
        enumeration_complete: bool,
        observed_epoch: int,
    ) -> "SurfaceObservationReceipt":
        kind = _exact_non_empty_string(surface_kind, "surface kind")
        if kind not in REQUIRED_SURFACE_KINDS:
            raise ValueError(f"unknown observation surface kind: {kind}")
        provider = _exact_non_empty_string(provider_id, "provider id")
        version = _exact_non_empty_string(provider_version, "provider version")
        locator = _exact_non_empty_string(source_locator, "source locator")
        scope = _exact_non_empty_string(scope_digest, "scope digest")
        state_digest = _exact_non_empty_string(observed_state_digest, "observed state digest")
        if type(enumeration_complete) is not bool:
            raise ValueError("enumeration_complete must be an exact boolean")
        epoch = _exact_epoch(observed_epoch)
        payload = {
            "protocol": SURFACE_RECEIPT_PROTOCOL,
            "surface_kind": kind,
            "provider_id": provider,
            "provider_version": version,
            "source_locator": locator,
            "scope_digest": scope,
            "observed_state_digest": state_digest,
            "enumeration_complete": enumeration_complete,
            "observed_epoch": epoch,
        }
        return cls(
            protocol=SURFACE_RECEIPT_PROTOCOL,
            surface_kind=kind,
            provider_id=provider,
            provider_version=version,
            source_locator=locator,
            scope_digest=scope,
            observed_state_digest=state_digest,
            enumeration_complete=enumeration_complete,
            observed_epoch=epoch,
            digest="surface-observation-receipt-v1-" + canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "surface_kind": self.surface_kind,
            "provider_id": self.provider_id,
            "provider_version": self.provider_version,
            "source_locator": self.source_locator,
            "scope_digest": self.scope_digest,
            "observed_state_digest": self.observed_state_digest,
            "enumeration_complete": self.enumeration_complete,
            "observed_epoch": self.observed_epoch,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "SurfaceObservationReceipt":
        if not isinstance(state, Mapping):
            raise ValueError("surface observation receipt state must be an object")
        _exact_keys(
            state,
            frozenset(
                {
                    "protocol",
                    "surface_kind",
                    "provider_id",
                    "provider_version",
                    "source_locator",
                    "scope_digest",
                    "observed_state_digest",
                    "enumeration_complete",
                    "observed_epoch",
                    "digest",
                }
            ),
            "surface observation receipt",
        )
        if state.get("protocol") != SURFACE_RECEIPT_PROTOCOL:
            raise ValueError("surface observation receipt protocol mismatch")
        expected = cls.create(
            surface_kind=state.get("surface_kind"),
            provider_id=state.get("provider_id"),
            provider_version=state.get("provider_version"),
            source_locator=state.get("source_locator"),
            scope_digest=state.get("scope_digest"),
            observed_state_digest=state.get("observed_state_digest"),
            enumeration_complete=state.get("enumeration_complete"),
            observed_epoch=state.get("observed_epoch"),
        )
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError("surface observation receipt state is non-canonical or digest-mismatched")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("surface observation receipt integrity validation failed") from exc
        if restored != self:
            raise ValueError("surface observation receipt integrity validation failed")


@dataclass(frozen=True, slots=True)
class CanonicalSurfaceProviderExpectation:
    surface_kind: str
    provider_id: str
    provider_version: str
    source_locator: str

    def __post_init__(self) -> None:
        kind = _exact_non_empty_string(self.surface_kind, "surface kind")
        if kind not in REQUIRED_SURFACE_KINDS:
            raise ValueError(f"unknown observation surface kind: {kind}")
        _exact_non_empty_string(self.provider_id, "provider id")
        _exact_non_empty_string(self.provider_version, "provider version")
        _exact_non_empty_string(self.source_locator, "source locator")


@dataclass(frozen=True, slots=True)
class CanonicalObservationEnvelope:
    protocol: str
    surface_contract: CanonicalObservationSurfaceContract
    observed_epoch: int
    registry_digest: str
    authority_graph_digest: str
    source_state_frontier_digest: str
    evidence_frontier_digest: str
    artifact_frontier_digest: str
    freshness_fence_frontier_digest: str
    handoff_frontier_digest: str
    work_trace_frontier_digest: str
    surface_receipts: tuple[SurfaceObservationReceipt, ...]
    chain_id: str
    previous_observation_digest: str | None
    digest: str

    @classmethod
    def create(
        cls,
        *,
        surface_contract: CanonicalObservationSurfaceContract,
        observed_epoch: int,
        registry_digest: str,
        authority_graph_digest: str,
        source_state_frontier_digest: str,
        evidence_frontier_digest: str,
        artifact_frontier_digest: str,
        freshness_fence_frontier_digest: str,
        handoff_frontier_digest: str,
        work_trace_frontier_digest: str,
        surface_receipts: Sequence[SurfaceObservationReceipt],
        chain_id: str,
        previous_observation_digest: str | None,
    ) -> "CanonicalObservationEnvelope":
        surface_contract.validate_integrity()
        epoch = _exact_epoch(observed_epoch)
        registry = _exact_non_empty_string(registry_digest, "registry digest")
        graph = _exact_non_empty_string(authority_graph_digest, "authority graph digest")
        source = _exact_non_empty_string(source_state_frontier_digest, "source-state frontier digest")
        evidence = _exact_non_empty_string(evidence_frontier_digest, "evidence frontier digest")
        artifact = _exact_non_empty_string(artifact_frontier_digest, "artifact frontier digest")
        freshness = _exact_non_empty_string(freshness_fence_frontier_digest, "freshness frontier digest")
        handoff = _exact_non_empty_string(handoff_frontier_digest, "handoff frontier digest")
        work_trace = _exact_non_empty_string(work_trace_frontier_digest, "work-trace frontier digest")
        chain = _exact_non_empty_string(chain_id, "chain id")
        predecessor: str | None
        if previous_observation_digest is None:
            predecessor = None
        else:
            predecessor = _exact_non_empty_string(
                previous_observation_digest,
                "previous observation digest",
            )

        receipts: list[SurfaceObservationReceipt] = []
        seen: set[str] = set()
        for receipt in surface_receipts:
            if not isinstance(receipt, SurfaceObservationReceipt):
                raise ValueError("surface observation receipt must use the canonical receipt type")
            receipt.validate_integrity()
            if receipt.surface_kind in seen:
                raise ValueError(f"duplicate surface observation receipt: {receipt.surface_kind}")
            seen.add(receipt.surface_kind)
            receipts.append(receipt)
        receipt_rows = tuple(sorted(receipts, key=lambda row: row.surface_kind))

        payload = {
            "protocol": OBSERVATION_PROTOCOL,
            "surface_contract": surface_contract.to_state(),
            "observed_epoch": epoch,
            "registry_digest": registry,
            "authority_graph_digest": graph,
            "source_state_frontier_digest": source,
            "evidence_frontier_digest": evidence,
            "artifact_frontier_digest": artifact,
            "freshness_fence_frontier_digest": freshness,
            "handoff_frontier_digest": handoff,
            "work_trace_frontier_digest": work_trace,
            "surface_receipts": [row.to_state() for row in receipt_rows],
            "chain_id": chain,
            "previous_observation_digest": predecessor,
        }
        return cls(
            protocol=OBSERVATION_PROTOCOL,
            surface_contract=surface_contract,
            observed_epoch=epoch,
            registry_digest=registry,
            authority_graph_digest=graph,
            source_state_frontier_digest=source,
            evidence_frontier_digest=evidence,
            artifact_frontier_digest=artifact,
            freshness_fence_frontier_digest=freshness,
            handoff_frontier_digest=handoff,
            work_trace_frontier_digest=work_trace,
            surface_receipts=receipt_rows,
            chain_id=chain,
            previous_observation_digest=predecessor,
            digest="canonical-observation-v1-" + canonical_digest(payload),
        )

    def to_state(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "surface_contract": self.surface_contract.to_state(),
            "observed_epoch": self.observed_epoch,
            "registry_digest": self.registry_digest,
            "authority_graph_digest": self.authority_graph_digest,
            "source_state_frontier_digest": self.source_state_frontier_digest,
            "evidence_frontier_digest": self.evidence_frontier_digest,
            "artifact_frontier_digest": self.artifact_frontier_digest,
            "freshness_fence_frontier_digest": self.freshness_fence_frontier_digest,
            "handoff_frontier_digest": self.handoff_frontier_digest,
            "work_trace_frontier_digest": self.work_trace_frontier_digest,
            "surface_receipts": [row.to_state() for row in self.surface_receipts],
            "chain_id": self.chain_id,
            "previous_observation_digest": self.previous_observation_digest,
            "digest": self.digest,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CanonicalObservationEnvelope":
        if not isinstance(state, Mapping):
            raise ValueError("canonical observation envelope state must be an object")
        _exact_keys(
            state,
            frozenset(
                {
                    "protocol",
                    "surface_contract",
                    "observed_epoch",
                    "registry_digest",
                    "authority_graph_digest",
                    "source_state_frontier_digest",
                    "evidence_frontier_digest",
                    "artifact_frontier_digest",
                    "freshness_fence_frontier_digest",
                    "handoff_frontier_digest",
                    "work_trace_frontier_digest",
                    "surface_receipts",
                    "chain_id",
                    "previous_observation_digest",
                    "digest",
                }
            ),
            "canonical observation envelope",
        )
        if state.get("protocol") != OBSERVATION_PROTOCOL:
            raise ValueError("canonical observation envelope protocol mismatch")
        raw_contract = state.get("surface_contract")
        if not isinstance(raw_contract, Mapping):
            raise ValueError("canonical observation surface contract must be an object")
        raw_receipts = state.get("surface_receipts")
        if type(raw_receipts) is not list:
            raise ValueError("canonical observation surface receipts must be a serialized list")
        contract = CanonicalObservationSurfaceContract.from_state(raw_contract)
        receipts = tuple(SurfaceObservationReceipt.from_state(row) for row in raw_receipts)
        expected = cls.create(
            surface_contract=contract,
            observed_epoch=state.get("observed_epoch"),
            registry_digest=state.get("registry_digest"),
            authority_graph_digest=state.get("authority_graph_digest"),
            source_state_frontier_digest=state.get("source_state_frontier_digest"),
            evidence_frontier_digest=state.get("evidence_frontier_digest"),
            artifact_frontier_digest=state.get("artifact_frontier_digest"),
            freshness_fence_frontier_digest=state.get("freshness_fence_frontier_digest"),
            handoff_frontier_digest=state.get("handoff_frontier_digest"),
            work_trace_frontier_digest=state.get("work_trace_frontier_digest"),
            surface_receipts=receipts,
            chain_id=state.get("chain_id"),
            previous_observation_digest=state.get("previous_observation_digest"),
        )
        if state.get("digest") != expected.digest or dict(state) != expected.to_state():
            raise ValueError("canonical observation envelope state is non-canonical or digest-mismatched")
        return expected

    def validate_integrity(self) -> None:
        try:
            restored = type(self).from_state(self.to_state())
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("canonical observation envelope integrity validation failed") from exc
        if restored != self:
            raise ValueError("canonical observation envelope integrity validation failed")

    def surface_receipt(self, surface_kind: str) -> SurfaceObservationReceipt:
        kind = _exact_non_empty_string(surface_kind, "surface kind")
        for receipt in self.surface_receipts:
            if receipt.surface_kind == kind:
                return receipt
        raise KeyError(kind)


def _surface_digest_map(envelope: CanonicalObservationEnvelope) -> dict[str, str]:
    return {
        "registry": envelope.registry_digest,
        "authority-graph": envelope.authority_graph_digest,
        "source-state": envelope.source_state_frontier_digest,
        "evidence": envelope.evidence_frontier_digest,
        "artifact": envelope.artifact_frontier_digest,
        "freshness": envelope.freshness_fence_frontier_digest,
        "handoff": envelope.handoff_frontier_digest,
        "work-trace": envelope.work_trace_frontier_digest,
    }


def validate_observation_completeness(
    envelope: CanonicalObservationEnvelope,
    *,
    expected_component_ids: Sequence[str],
    observed_surface_digests: Mapping[str, str],
    expected_scope_digests: Mapping[str, str] | None = None,
) -> tuple[ObservationFinding, ...]:
    envelope.validate_integrity()
    expected_components = _validated_component_ids(expected_component_ids)
    actual_components = envelope.surface_contract.required_component_ids
    findings: list[ObservationFinding] = []

    expected_set = set(expected_components)
    actual_set = set(actual_components)
    for component_id in sorted(expected_set - actual_set):
        findings.append(
            ObservationFinding(
                code="OBSERVATION_REQUIRED_COMPONENT_MISSING",
                detail="required canonical component is absent from the observation contract",
                subject_id=component_id,
            )
        )
    for component_id in sorted(actual_set - expected_set):
        findings.append(
            ObservationFinding(
                code="OBSERVATION_UNEXPECTED_COMPONENT",
                detail="observation contract contains an unexpected canonical component",
                subject_id=component_id,
            )
        )

    receipt_by_kind: dict[str, SurfaceObservationReceipt] = {}
    duplicate_kinds: set[str] = set()
    unexpected_kinds: set[str] = set()
    for receipt in envelope.surface_receipts:
        if receipt.surface_kind in receipt_by_kind:
            duplicate_kinds.add(receipt.surface_kind)
        receipt_by_kind[receipt.surface_kind] = receipt
        if receipt.surface_kind not in REQUIRED_SURFACE_KINDS:
            unexpected_kinds.add(receipt.surface_kind)
    for kind in sorted(duplicate_kinds):
        findings.append(
            ObservationFinding(
                code="OBSERVATION_SURFACE_DUPLICATE",
                detail="observation contains more than one receipt for the same surface",
                subject_id=kind,
            )
        )
    for kind in sorted(unexpected_kinds):
        findings.append(
            ObservationFinding(
                code="OBSERVATION_SURFACE_UNEXPECTED",
                detail="observation contains a receipt for an undeclared surface",
                subject_id=kind,
            )
        )

    committed_digests = _surface_digest_map(envelope)
    for kind in REQUIRED_SURFACE_KINDS:
        receipt = receipt_by_kind.get(kind)
        if receipt is None:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_REQUIRED_SURFACE_MISSING",
                    detail="required observation surface has no completeness receipt",
                    subject_id=kind,
                )
            )
            continue
        if not receipt.enumeration_complete:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_ENUMERATION_INCOMPLETE",
                    detail="required observation surface did not declare complete enumeration",
                    subject_id=kind,
                )
            )
        if receipt.observed_epoch != envelope.observed_epoch:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_SURFACE_EPOCH_MISMATCH",
                    detail="surface receipt epoch does not match the observation envelope epoch",
                    subject_id=kind,
                )
            )
        observed_digest = observed_surface_digests.get(kind)
        if observed_digest is None or receipt.observed_state_digest != observed_digest:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_SURFACE_STATE_DIGEST_MISMATCH",
                    detail="surface receipt content digest does not match the detached observed surface",
                    subject_id=kind,
                )
            )
        if receipt.observed_state_digest != committed_digests[kind]:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_SURFACE_STATE_DIGEST_MISMATCH",
                    detail="surface receipt content digest does not match the envelope commitment",
                    subject_id=kind,
                )
            )
        if expected_scope_digests is not None:
            expected_scope = expected_scope_digests.get(kind)
            if expected_scope is None or receipt.scope_digest != expected_scope:
                findings.append(
                    ObservationFinding(
                        code="OBSERVATION_SURFACE_SCOPE_MISMATCH",
                        detail="surface receipt scope does not match the canonical declared scope",
                        subject_id=kind,
                    )
                )

    return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))


def validate_observation_provenance(
    envelope: CanonicalObservationEnvelope,
    *,
    provider_expectations: Mapping[str, CanonicalSurfaceProviderExpectation],
    expected_scope_digests: Mapping[str, str] | None = None,
) -> tuple[ObservationFinding, ...]:
    envelope.validate_integrity()
    committed_digests = _surface_digest_map(envelope)
    findings: list[ObservationFinding] = []

    for kind in REQUIRED_SURFACE_KINDS:
        try:
            receipt = envelope.surface_receipt(kind)
        except KeyError:
            continue
        try:
            receipt.validate_integrity()
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_RECEIPT_FORGED",
                    detail=str(exc),
                    subject_id=kind,
                )
            )
            continue

        expectation = provider_expectations.get(kind)
        if expectation is None:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_PROVIDER_ID_MISMATCH",
                    detail="canonical provider expectation is unavailable for the observed surface",
                    subject_id=kind,
                )
            )
        else:
            if expectation.surface_kind != kind:
                findings.append(
                    ObservationFinding(
                        code="OBSERVATION_PROVIDER_ID_MISMATCH",
                        detail="provider expectation is bound to another surface kind",
                        subject_id=kind,
                    )
                )
            if receipt.provider_id != expectation.provider_id:
                findings.append(
                    ObservationFinding(
                        code="OBSERVATION_PROVIDER_ID_MISMATCH",
                        detail="surface receipt provider identity does not match the canonical expectation",
                        subject_id=kind,
                    )
                )
            if receipt.provider_version != expectation.provider_version:
                findings.append(
                    ObservationFinding(
                        code="OBSERVATION_PROVIDER_VERSION_MISMATCH",
                        detail="surface receipt provider version does not match the canonical expectation",
                        subject_id=kind,
                    )
                )
            if receipt.source_locator != expectation.source_locator:
                findings.append(
                    ObservationFinding(
                        code="OBSERVATION_SOURCE_LOCATOR_MISMATCH",
                        detail="surface receipt source locator does not match the canonical expectation",
                        subject_id=kind,
                    )
                )

        if receipt.observed_epoch != envelope.observed_epoch:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_PROVENANCE_EPOCH_MISMATCH",
                    detail="surface provenance epoch does not match the observation envelope epoch",
                    subject_id=kind,
                )
            )
        if receipt.observed_state_digest != committed_digests[kind]:
            findings.append(
                ObservationFinding(
                    code="OBSERVATION_PROVENANCE_CONTENT_MISMATCH",
                    detail="surface provenance content digest does not match the observation commitment",
                    subject_id=kind,
                )
            )
        if expected_scope_digests is not None:
            expected_scope = expected_scope_digests.get(kind)
            if expected_scope is None or receipt.scope_digest != expected_scope:
                findings.append(
                    ObservationFinding(
                        code="OBSERVATION_PROVENANCE_SCOPE_MISMATCH",
                        detail="surface provenance scope does not match the canonical expectation",
                        subject_id=kind,
                    )
                )

    return tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))


__all__ = (
    "CanonicalObservationEnvelope",
    "CanonicalObservationSurfaceContract",
    "CanonicalSurfaceProviderExpectation",
    "OBSERVATION_PROTOCOL",
    "OBSERVATION_SURFACE_PROTOCOL",
    "ObservationFinding",
    "REQUIRED_SURFACE_KINDS",
    "SURFACE_RECEIPT_PROTOCOL",
    "SurfaceObservationReceipt",
    "validate_observation_completeness",
    "validate_observation_provenance",
)
