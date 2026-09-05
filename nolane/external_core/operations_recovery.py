from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.artifact_provenance import ArtifactCurrentness
from nolane.external_core.artifacts import ArtifactStore
from nolane.external_core.assurance import AssuranceDisposition
from nolane.external_core.operations_journal import OperationsJournal


class RecoveryMode(str, Enum):
    EXACT = "exact"
    FAST_FORWARD = "fast_forward"
    QUARANTINED = "quarantined"


class CurrentReleaseDisposition(str, Enum):
    READY = "ready"
    READY_WITH_EXPLICIT_OVERRIDE = "ready_with_explicit_override"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class OperationsSnapshot:
    snapshot_id: str
    component_versions: tuple[tuple[str, str], ...]
    journal_head_digest: str
    journal_length: int
    artifact_graph_digest: str
    authority_graph_digest: str
    readiness_state_digest: str
    registry_digest: str
    active_operation_ids: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "component_versions": {key: value for key, value in self.component_versions},
            "journal_head_digest": self.journal_head_digest,
            "journal_length": self.journal_length,
            "artifact_graph_digest": self.artifact_graph_digest,
            "authority_graph_digest": self.authority_graph_digest,
            "readiness_state_digest": self.readiness_state_digest,
            "registry_digest": self.registry_digest,
            "active_operation_ids": list(self.active_operation_ids),
        }

    def to_state(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, **self.payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        component_versions: Mapping[str, str],
        journal_head_digest: str,
        journal_length: int,
        artifact_graph_digest: str,
        authority_graph_digest: str,
        readiness_state_digest: str,
        registry_digest: str,
        active_operation_ids: tuple[str, ...],
    ) -> "OperationsSnapshot":
        versions = _normalize_mapping(component_versions, "component version")
        length = _non_negative_int(journal_length, "journal_length")
        active = _unique_explicit(active_operation_ids, "active operation id")
        head = str(journal_head_digest)
        if length == 0 and head:
            raise ValueError("empty operations snapshot cannot carry a journal head")
        if length > 0 and not head.strip():
            raise ValueError("non-empty operations snapshot requires a journal head")
        payload = {
            "component_versions": {key: value for key, value in versions},
            "journal_head_digest": head,
            "journal_length": length,
            "artifact_graph_digest": _explicit(artifact_graph_digest, "artifact graph digest"),
            "authority_graph_digest": _explicit(authority_graph_digest, "authority graph digest"),
            "readiness_state_digest": _explicit(readiness_state_digest, "readiness state digest"),
            "registry_digest": _explicit(registry_digest, "registry digest"),
            "active_operation_ids": list(active),
        }
        digest = canonical_digest(payload)
        return cls(
            snapshot_id="operations-snapshot-" + digest[:24],
            component_versions=versions,
            journal_head_digest=head,
            journal_length=length,
            artifact_graph_digest=payload["artifact_graph_digest"],
            authority_graph_digest=payload["authority_graph_digest"],
            readiness_state_digest=payload["readiness_state_digest"],
            registry_digest=payload["registry_digest"],
            active_operation_ids=active,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "OperationsSnapshot":
        versions_raw = state.get("component_versions", {})
        if not isinstance(versions_raw, Mapping):
            raise ValueError("operations snapshot component_versions must be an object")
        expected = cls.create(
            component_versions={str(k): str(v) for k, v in versions_raw.items()},
            journal_head_digest=str(state.get("journal_head_digest", "")),
            journal_length=state["journal_length"],
            artifact_graph_digest=str(state["artifact_graph_digest"]),
            authority_graph_digest=str(state["authority_graph_digest"]),
            readiness_state_digest=str(state["readiness_state_digest"]),
            registry_digest=str(state["registry_digest"]),
            active_operation_ids=tuple(str(x) for x in state.get("active_operation_ids", ())),
        )
        if str(state.get("snapshot_id", "")) != expected.snapshot_id:
            raise ValueError("operations snapshot identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("operations snapshot digest mismatch")
        return expected


@dataclass(frozen=True, slots=True)
class RecoveryCertificate:
    certificate_id: str
    snapshot_id: str
    snapshot_digest: str
    current_journal_head_digest: str
    current_journal_length: int
    mode: RecoveryMode
    authoritative: bool
    reasons: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_digest": self.snapshot_digest,
            "current_journal_head_digest": self.current_journal_head_digest,
            "current_journal_length": self.current_journal_length,
            "mode": self.mode.value,
            "authoritative": self.authoritative,
            "reasons": list(self.reasons),
        }

    def to_state(self) -> dict[str, Any]:
        return {"certificate_id": self.certificate_id, **self.payload(), "digest": self.digest}


@dataclass(frozen=True, slots=True)
class OperationalLease:
    lease_id: str
    resource_id: str
    owner_id: str
    fence_epoch: int
    issued_epoch: int
    expires_epoch: int
    predecessor_lease_id: str | None
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "owner_id": self.owner_id,
            "fence_epoch": self.fence_epoch,
            "issued_epoch": self.issued_epoch,
            "expires_epoch": self.expires_epoch,
            "predecessor_lease_id": self.predecessor_lease_id,
        }


@dataclass(frozen=True, slots=True)
class OperationalLeaseRelease:
    release_id: str
    lease_id: str
    resource_id: str
    owner_id: str
    fence_epoch: int
    terminal_ref: str
    digest: str


class OperationalLeaseRegistry:
    """Fence ownership for G-owned operational resources only."""

    def __init__(self) -> None:
        self._active: dict[str, OperationalLease] = {}
        self._last: dict[str, OperationalLease] = {}
        self._fences: dict[str, int] = {}
        self._releases: dict[str, OperationalLeaseRelease] = {}

    def acquire(
        self,
        *,
        resource_id: str,
        owner_id: str,
        issued_epoch: int,
        expires_epoch: int,
    ) -> OperationalLease:
        resource = _explicit(resource_id, "operational lease resource id")
        owner = _explicit(owner_id, "operational lease owner id")
        issued = _non_negative_int(issued_epoch, "issued_epoch")
        expires = _non_negative_int(expires_epoch, "expires_epoch")
        if expires <= issued:
            raise ValueError("operational lease expiry must be after issue epoch")
        if resource in self._active:
            raise PermissionError("operational resource already has an active lease")
        fence = self._fences.get(resource, 0) + 1
        predecessor = self._last.get(resource)
        payload = {
            "resource_id": resource,
            "owner_id": owner,
            "fence_epoch": fence,
            "issued_epoch": issued,
            "expires_epoch": expires,
            "predecessor_lease_id": None if predecessor is None else predecessor.lease_id,
        }
        digest = canonical_digest(payload)
        lease = OperationalLease(
            lease_id="operations-lease-" + digest[:24],
            resource_id=resource,
            owner_id=owner,
            fence_epoch=fence,
            issued_epoch=issued,
            expires_epoch=expires,
            predecessor_lease_id=payload["predecessor_lease_id"],
            digest=digest,
        )
        self._active[resource] = lease
        self._last[resource] = lease
        self._fences[resource] = fence
        return lease

    def release(
        self,
        *,
        resource_id: str,
        owner_id: str,
        fence_epoch: int,
        terminal_ref: str,
    ) -> OperationalLeaseRelease:
        resource = _explicit(resource_id, "operational lease resource id")
        fence = _non_negative_int(fence_epoch, "fence_epoch")
        active = self._active.get(resource)
        if active is None or active.fence_epoch != fence:
            raise PermissionError("stale fence cannot release operational resource")
        if active.owner_id != str(owner_id):
            raise PermissionError("operational lease owner mismatch")
        payload = {
            "lease_id": active.lease_id,
            "resource_id": resource,
            "owner_id": active.owner_id,
            "fence_epoch": active.fence_epoch,
            "terminal_ref": _explicit(terminal_ref, "operational lease terminal ref"),
        }
        digest = canonical_digest(payload)
        row = OperationalLeaseRelease(
            release_id="operations-lease-release-" + digest[:24],
            lease_id=active.lease_id,
            resource_id=resource,
            owner_id=active.owner_id,
            fence_epoch=active.fence_epoch,
            terminal_ref=payload["terminal_ref"],
            digest=digest,
        )
        self._releases[row.release_id] = row
        del self._active[resource]
        return row


@dataclass(frozen=True, slots=True)
class ReleaseCurrentnessBasis:
    release_id: str
    package_artifact_id: str
    rollback_artifact_id: str
    build_reproducible: bool | None
    observability_current: bool | None
    reliability_current: bool | None
    assurance_disposition: AssuranceDisposition | None
    source_baseline_current: bool | None
    allow_assurance_override: bool = False

    def __post_init__(self) -> None:
        _explicit(self.release_id, "release id")
        _explicit(self.package_artifact_id, "package artifact id")
        _explicit(self.rollback_artifact_id, "rollback artifact id")
        for name in (
            "build_reproducible",
            "observability_current",
            "reliability_current",
            "source_baseline_current",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{name} must be bool or None")
        if not isinstance(self.allow_assurance_override, bool):
            raise TypeError("allow_assurance_override must be bool")


@dataclass(frozen=True, slots=True)
class CurrentReleaseReadinessAssessment:
    assessment_id: str
    release_id: str
    package_status: ArtifactCurrentness | None
    rollback_status: ArtifactCurrentness | None
    assurance_disposition: AssuranceDisposition | None
    disposition: CurrentReleaseDisposition
    reasons: tuple[str, ...]
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "package_status": None if self.package_status is None else self.package_status.value,
            "rollback_status": None if self.rollback_status is None else self.rollback_status.value,
            "assurance_disposition": None if self.assurance_disposition is None else self.assurance_disposition.value,
            "disposition": self.disposition.value,
            "reasons": list(self.reasons),
        }


def recover_operations(
    *,
    snapshot: OperationsSnapshot,
    journal: OperationsJournal,
    current_artifact_graph_digest: str,
    current_authority_graph_digest: str,
    current_readiness_state_digest: str,
    current_registry_digest: str,
) -> RecoveryCertificate:
    reasons: list[str] = []
    if snapshot.artifact_graph_digest != str(current_artifact_graph_digest):
        reasons.append("artifact_graph_digest_drift")
    if snapshot.authority_graph_digest != str(current_authority_graph_digest):
        reasons.append("authority_graph_digest_drift")
    if snapshot.readiness_state_digest != str(current_readiness_state_digest):
        reasons.append("readiness_state_digest_drift")
    if snapshot.registry_digest != str(current_registry_digest):
        reasons.append("registry_digest_drift")
    if snapshot.journal_length > journal.length:
        reasons.append("journal_history_truncated")
    else:
        try:
            prefix_head = journal.digest_at_length(snapshot.journal_length)
        except KeyError:
            prefix_head = ""
            reasons.append("journal_prefix_unavailable")
        if prefix_head != snapshot.journal_head_digest:
            reasons.append("journal_history_diverged")

    if reasons:
        mode = RecoveryMode.QUARANTINED
        authoritative = False
    elif snapshot.journal_length == journal.length:
        mode = RecoveryMode.EXACT
        authoritative = True
    else:
        mode = RecoveryMode.FAST_FORWARD
        authoritative = True

    normalized = tuple(dict.fromkeys(reasons))
    payload = {
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_digest": snapshot.digest,
        "current_journal_head_digest": journal.head_digest,
        "current_journal_length": journal.length,
        "mode": mode.value,
        "authoritative": authoritative,
        "reasons": list(normalized),
    }
    digest = canonical_digest(payload)
    return RecoveryCertificate(
        certificate_id="operations-recovery-" + digest[:24],
        snapshot_id=snapshot.snapshot_id,
        snapshot_digest=snapshot.digest,
        current_journal_head_digest=journal.head_digest,
        current_journal_length=journal.length,
        mode=mode,
        authoritative=authoritative,
        reasons=normalized,
        digest=digest,
    )


def assess_current_release_readiness(
    *,
    basis: ReleaseCurrentnessBasis,
    artifacts: ArtifactStore,
    current_epoch: int,
) -> CurrentReleaseReadinessAssessment:
    epoch = _non_negative_int(current_epoch, "current_epoch")
    blocking: list[str] = []
    unknown: list[str] = []
    package_status: ArtifactCurrentness | None = None
    rollback_status: ArtifactCurrentness | None = None

    try:
        package_status = artifacts.currentness(
            basis.package_artifact_id, current_epoch=epoch
        ).status
    except KeyError:
        unknown.append("package_currentness_unknown")
    else:
        if package_status is ArtifactCurrentness.UNKNOWN:
            unknown.append("package_currentness_unknown")
        elif package_status is not ArtifactCurrentness.CURRENT:
            blocking.append("package_not_current")

    try:
        rollback_status = artifacts.currentness(
            basis.rollback_artifact_id, current_epoch=epoch
        ).status
    except KeyError:
        unknown.append("rollback_currentness_unknown")
    else:
        if rollback_status is ArtifactCurrentness.UNKNOWN:
            unknown.append("rollback_currentness_unknown")
        elif rollback_status is not ArtifactCurrentness.CURRENT:
            blocking.append("rollback_not_current")

    _tri_state_reason(
        basis.build_reproducible,
        false_code="build_not_reproducible",
        unknown_code="build_reproducibility_unknown",
        blocking=blocking,
        unknown=unknown,
    )
    _tri_state_reason(
        basis.observability_current,
        false_code="observability_not_current",
        unknown_code="observability_currentness_unknown",
        blocking=blocking,
        unknown=unknown,
    )
    _tri_state_reason(
        basis.reliability_current,
        false_code="reliability_not_current",
        unknown_code="reliability_currentness_unknown",
        blocking=blocking,
        unknown=unknown,
    )
    _tri_state_reason(
        basis.source_baseline_current,
        false_code="source_baseline_drift",
        unknown_code="source_baseline_currentness_unknown",
        blocking=blocking,
        unknown=unknown,
    )

    assurance = basis.assurance_disposition
    override_ready = False
    if assurance is None or assurance is AssuranceDisposition.PENDING:
        unknown.append("assurance_currentness_unknown")
    elif assurance is AssuranceDisposition.VERIFIED:
        pass
    elif assurance is AssuranceDisposition.OVERRIDDEN and basis.allow_assurance_override:
        override_ready = True
    else:
        blocking.append("assurance_not_currently_verified")

    if blocking:
        disposition = CurrentReleaseDisposition.BLOCKED
        reasons = tuple(dict.fromkeys(blocking + unknown))
    elif unknown:
        disposition = CurrentReleaseDisposition.UNKNOWN
        reasons = tuple(dict.fromkeys(unknown))
    elif override_ready:
        disposition = CurrentReleaseDisposition.READY_WITH_EXPLICIT_OVERRIDE
        reasons = ()
    else:
        disposition = CurrentReleaseDisposition.READY
        reasons = ()

    payload = {
        "release_id": basis.release_id,
        "package_status": None if package_status is None else package_status.value,
        "rollback_status": None if rollback_status is None else rollback_status.value,
        "assurance_disposition": None if assurance is None else assurance.value,
        "disposition": disposition.value,
        "reasons": list(reasons),
    }
    digest = canonical_digest(payload)
    return CurrentReleaseReadinessAssessment(
        assessment_id="current-release-readiness-" + digest[:24],
        release_id=basis.release_id,
        package_status=package_status,
        rollback_status=rollback_status,
        assurance_disposition=assurance,
        disposition=disposition,
        reasons=reasons,
        digest=digest,
    )


def _tri_state_reason(
    value: bool | None,
    *,
    false_code: str,
    unknown_code: str,
    blocking: list[str],
    unknown: list[str],
) -> None:
    if value is None:
        unknown.append(unknown_code)
    elif value is False:
        blocking.append(false_code)


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer, not bool")
    if value < 0:
        raise ValueError(f"{label} must be non-negative")
    return value


def _unique_explicit(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    rows = tuple(str(value) for value in values)
    if any(not value.strip() for value in rows):
        raise ValueError(f"{label} must be explicit")
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


def _normalize_mapping(values: Mapping[str, str], label: str) -> tuple[tuple[str, str], ...]:
    rows = tuple(sorted((str(key), str(value)) for key, value in values.items()))
    if any(not key.strip() or not value.strip() for key, value in rows):
        raise ValueError(f"{label} keys and values must be explicit")
    if len({key for key, _ in rows}) != len(rows):
        raise ValueError(f"duplicate {label} key")
    return rows


__all__ = (
    "CurrentReleaseDisposition",
    "CurrentReleaseReadinessAssessment",
    "OperationalLease",
    "OperationalLeaseRegistry",
    "OperationalLeaseRelease",
    "OperationsSnapshot",
    "RecoveryCertificate",
    "RecoveryMode",
    "ReleaseCurrentnessBasis",
    "assess_current_release_readiness",
    "recover_operations",
)
