"""Deterministic public revision history for D. Goal / Design integrity contracts.

The history layer is a read-only projection over already-installed Goal Integrity
contracts, predecessor topology, evolution receipts, and runtime trust
provenance. It cannot authorize a revision and never rewrites historical
contract or evolution-receipt identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from .goal_design import stable_digest
from .goal_design_integrity import GoalIntegrityContract
from .goal_design_integrity_evolution import (
    LEGACY_UNATTESTED_TRUST,
    GoalIntegrityEvolutionReceipt,
    verify_goal_integrity_evolution_receipt,
)

__version__ = "0.1.1"

GOAL_REVISION_HISTORY_PROTOCOL = "nolane.goal_revision_history"
GOAL_REVISION_HISTORY_MAJOR = 1
GOAL_REVISION_HISTORY_MINOR = 0
ROOT_INTEGRITY_CONTRACT_TRUST = "root_integrity_contract"

# Kept local to avoid a reverse import from the projection layer into the
# runtime module that owns these public trust labels.
_VERIFIED_CAPABILITY_AUTHORITY_TRUST = "verified_capability_authority"
_LEGACY_UNVERIFIED_AUTHORITY_TRUST = "legacy_unverified_authority"
_RECEIPTED_REVISION_TRUSTS = frozenset(
    {
        _VERIFIED_CAPABILITY_AUTHORITY_TRUST,
        _LEGACY_UNVERIFIED_AUTHORITY_TRUST,
    }
)

_MAX_TEXT = 4096
_MAX_REF = 512
_MAX_REFS = 64
_MAX_STEPS = 16
_MAX_HISTORY_ENTRIES = 4096

_FEATURES = (
    "canonical_entry_chain",
    "explicit_trust_provenance",
    "local_deterministic_projection",
    "restart_verifiable_receipt",
    "truthful_legacy_missingness",
)
_ROOT_TRANSFORMATION_HISTORY = (
    "goal_integrity_contract:v1",
    "goal_revision_history_projection:v1",
)
_LEGACY_TRANSFORMATION_HISTORY = (
    "goal_integrity_contract:v1",
    "legacy_unattested_revision:v1",
    "goal_revision_history_projection:v1",
)
_RECEIPTED_TRANSFORMATION_HISTORY = (
    "goal_integrity_contract:v1",
    "goal_integrity_evolution_receipt:v1",
    "goal_revision_history_projection:v1",
)


def _text(name: str, value: object, *, limit: int = _MAX_TEXT) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    if len(normalized) > limit:
        raise ValueError(f"{name} exceeds bounded field limit")
    return normalized


def _optional_text(name: str, value: object | None, *, limit: int = _MAX_REF) -> str | None:
    if value is None:
        return None
    return _text(name, value, limit=limit)


def _refs(name: str, values: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(sorted({_text(name, value, limit=_MAX_REF) for value in values}))
    if len(normalized) > _MAX_REFS:
        raise ValueError(f"{name} exceeds bounded reference count")
    return normalized


def _steps(values: Iterable[str]) -> tuple[str, ...]:
    steps = tuple(_text("transformation_step", value, limit=_MAX_REF) for value in values)
    if not steps:
        raise ValueError("transformation_history requires at least one step")
    if len(steps) > _MAX_STEPS:
        raise ValueError("transformation_history exceeds bounded step count")
    if len(set(steps)) != len(steps):
        raise ValueError("transformation_history cannot contain duplicate steps")
    return steps


def _contract_provenance(contract: GoalIntegrityContract) -> tuple[str, ...]:
    return _refs(
        "contract_provenance_ref",
        tuple(clause.provenance_ref for clause in contract.clauses)
        + tuple(binding.provenance_ref for binding in contract.metric_bindings),
    )


def _capability_payload(capability: "GoalRevisionHistoryCapability") -> dict[str, object]:
    return {
        "protocol_name": capability.protocol_name,
        "major": capability.major,
        "minor": capability.minor,
        "features": capability.features,
    }


@dataclass(frozen=True)
class GoalRevisionHistoryCapability:
    """Negotiated version/capability contract for public history export."""

    protocol_name: str = GOAL_REVISION_HISTORY_PROTOCOL
    major: int = GOAL_REVISION_HISTORY_MAJOR
    minor: int = GOAL_REVISION_HISTORY_MINOR
    features: tuple[str, ...] = _FEATURES
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "protocol_name",
            _text("protocol_name", self.protocol_name, limit=_MAX_REF),
        )
        major = int(self.major)
        minor = int(self.minor)
        if major < 0 or minor < 0:
            raise ValueError("history protocol versions must be non-negative")
        object.__setattr__(self, "major", major)
        object.__setattr__(self, "minor", minor)
        features = _refs("history_feature", self.features)
        if not features:
            raise ValueError("history capability requires features")
        object.__setattr__(self, "features", features)
        object.__setattr__(
            self,
            "digest",
            stable_digest({"goal_revision_history_capability": _capability_payload(self)}),
        )


def _entry_payload(entry: "GoalRevisionHistoryEntry") -> dict[str, object]:
    return {
        "goal_id": entry.goal_id,
        "ordinal": entry.ordinal,
        "contract_digest": entry.contract_digest,
        "predecessor_digest": entry.predecessor_digest,
        "evolution_receipt_id": entry.evolution_receipt_id,
        "delta_digest": entry.delta_digest,
        "trust_label": entry.trust_label,
        "source_refs": entry.source_refs,
        "evidence_refs": entry.evidence_refs,
        "freshness_ref": entry.freshness_ref,
        "confidence_milli": entry.confidence_milli,
        "transformation_history": entry.transformation_history,
        "previous_entry_digest": entry.previous_entry_digest,
    }


@dataclass(frozen=True)
class GoalRevisionHistoryEntry:
    """One immutable node in the root-to-current Goal Integrity revision chain."""

    goal_id: str
    ordinal: int
    contract_digest: str
    trust_label: str
    predecessor_digest: str | None = None
    evolution_receipt_id: str | None = None
    delta_digest: str | None = None
    source_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    freshness_ref: str | None = None
    confidence_milli: int | None = None
    transformation_history: tuple[str, ...] = ("goal_revision_history_projection:v1",)
    previous_entry_digest: str | None = None
    entry_digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal_id", _text("goal_id", self.goal_id, limit=_MAX_REF))
        object.__setattr__(
            self,
            "contract_digest",
            _text("contract_digest", self.contract_digest, limit=_MAX_REF),
        )
        object.__setattr__(
            self,
            "trust_label",
            _text("trust_label", self.trust_label, limit=_MAX_REF),
        )
        ordinal = int(self.ordinal)
        if ordinal < 0 or ordinal >= _MAX_HISTORY_ENTRIES:
            raise ValueError("history ordinal exceeds bounded range")
        object.__setattr__(self, "ordinal", ordinal)
        for name in (
            "predecessor_digest",
            "evolution_receipt_id",
            "delta_digest",
            "freshness_ref",
            "previous_entry_digest",
        ):
            object.__setattr__(
                self,
                name,
                _optional_text(name, getattr(self, name), limit=_MAX_REF),
            )
        object.__setattr__(self, "source_refs", _refs("source_ref", self.source_refs))
        object.__setattr__(self, "evidence_refs", _refs("evidence_ref", self.evidence_refs))
        object.__setattr__(
            self,
            "transformation_history",
            _steps(self.transformation_history),
        )
        confidence = self.confidence_milli
        if confidence is not None:
            confidence = int(confidence)
            if confidence < 0 or confidence > 1000:
                raise ValueError("confidence_milli must be between 0 and 1000")
            object.__setattr__(self, "confidence_milli", confidence)

        if ordinal == 0:
            if any(
                value is not None
                for value in (
                    self.predecessor_digest,
                    self.evolution_receipt_id,
                    self.delta_digest,
                    self.freshness_ref,
                    self.confidence_milli,
                    self.previous_entry_digest,
                )
            ):
                raise ValueError("root history entry cannot claim revision authority metadata")
        else:
            if self.predecessor_digest is None or self.previous_entry_digest is None:
                raise ValueError("non-root history entry requires predecessor and previous entry")
            if (self.evolution_receipt_id is None) != (self.delta_digest is None):
                raise ValueError("revision receipt and delta must be present or absent together")
            if self.evolution_receipt_id is None and (
                self.freshness_ref is not None or self.confidence_milli is not None
            ):
                raise ValueError(
                    "receiptless revision cannot fabricate freshness or confidence"
                )

        object.__setattr__(
            self,
            "entry_digest",
            stable_digest({"goal_revision_history_entry": _entry_payload(self)}),
        )


def _snapshot_payload(snapshot: "GoalRevisionHistorySnapshot") -> dict[str, object]:
    return {
        "capability_digest": snapshot.capability.digest,
        "goal_id": snapshot.goal_id,
        "current_contract_digest": snapshot.current_contract_digest,
        "entry_digests": tuple(entry.entry_digest for entry in snapshot.entries),
    }


@dataclass(frozen=True)
class GoalRevisionHistorySnapshot:
    """Canonical deterministic public record for one goal's complete revision chain."""

    capability: GoalRevisionHistoryCapability
    goal_id: str
    current_contract_digest: str
    entries: tuple[GoalRevisionHistoryEntry, ...]
    history_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.capability, GoalRevisionHistoryCapability):
            raise TypeError("history snapshot requires GoalRevisionHistoryCapability")
        object.__setattr__(self, "goal_id", _text("goal_id", self.goal_id, limit=_MAX_REF))
        object.__setattr__(
            self,
            "current_contract_digest",
            _text("current_contract_digest", self.current_contract_digest, limit=_MAX_REF),
        )
        entries = tuple(self.entries)
        if not entries:
            raise ValueError("history snapshot requires at least one entry")
        if len(entries) > _MAX_HISTORY_ENTRIES:
            raise ValueError("history snapshot exceeds bounded entry count")
        if len({entry.contract_digest for entry in entries}) != len(entries):
            raise ValueError("history snapshot contains duplicate contract identity")
        for ordinal, entry in enumerate(entries):
            if entry.goal_id != self.goal_id:
                raise ValueError("history entry belongs to a different goal")
            if entry.ordinal != ordinal:
                raise ValueError("history ordinals must be contiguous from root")
            if ordinal == 0:
                if entry.previous_entry_digest is not None:
                    raise ValueError("root history entry cannot link to a previous entry")
            elif entry.previous_entry_digest != entries[ordinal - 1].entry_digest:
                raise ValueError("history entry chain digest mismatch")
        if entries[-1].contract_digest != self.current_contract_digest:
            raise ValueError("history current contract does not match chain head")
        object.__setattr__(self, "entries", entries)
        object.__setattr__(
            self,
            "history_digest",
            stable_digest({"goal_revision_history_snapshot": _snapshot_payload(self)}),
        )


def _receipt_payload(receipt: "GoalRevisionHistoryReceipt") -> dict[str, object]:
    return {
        "protocol_major": receipt.protocol_major,
        "protocol_minor": receipt.protocol_minor,
        "goal_id": receipt.goal_id,
        "history_digest": receipt.history_digest,
        "current_contract_digest": receipt.current_contract_digest,
        "entry_count": receipt.entry_count,
    }


@dataclass(frozen=True)
class GoalRevisionHistoryReceipt:
    """Tamper-evident deterministic receipt for one public history snapshot."""

    protocol_major: int
    protocol_minor: int
    goal_id: str
    history_digest: str
    current_contract_digest: str
    entry_count: int
    receipt_id: str = field(init=False)

    def __post_init__(self) -> None:
        major = int(self.protocol_major)
        minor = int(self.protocol_minor)
        count = int(self.entry_count)
        if major < 0 or minor < 0:
            raise ValueError("history receipt protocol versions must be non-negative")
        if count <= 0 or count > _MAX_HISTORY_ENTRIES:
            raise ValueError("history receipt entry count exceeds bounded range")
        object.__setattr__(self, "protocol_major", major)
        object.__setattr__(self, "protocol_minor", minor)
        object.__setattr__(self, "entry_count", count)
        for name in ("goal_id", "history_digest", "current_contract_digest"):
            object.__setattr__(
                self,
                name,
                _text(name, getattr(self, name), limit=_MAX_REF),
            )
        object.__setattr__(
            self,
            "receipt_id",
            stable_digest({"goal_revision_history_receipt": _receipt_payload(self)}),
        )


@dataclass(frozen=True)
class GoalRevisionHistoryExport:
    snapshot: GoalRevisionHistorySnapshot
    receipt: GoalRevisionHistoryReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot, GoalRevisionHistorySnapshot):
            raise TypeError("history export requires GoalRevisionHistorySnapshot")
        if not isinstance(self.receipt, GoalRevisionHistoryReceipt):
            raise TypeError("history export requires GoalRevisionHistoryReceipt")
        if self.receipt.goal_id != self.snapshot.goal_id:
            raise ValueError("history receipt goal does not bind snapshot")
        if self.receipt.history_digest != self.snapshot.history_digest:
            raise ValueError("history receipt digest does not bind snapshot")
        if self.receipt.current_contract_digest != self.snapshot.current_contract_digest:
            raise ValueError("history receipt current head does not bind snapshot")
        if self.receipt.entry_count != len(self.snapshot.entries):
            raise ValueError("history receipt entry count does not bind snapshot")
        if (
            self.receipt.protocol_major != self.snapshot.capability.major
            or self.receipt.protocol_minor != self.snapshot.capability.minor
        ):
            raise ValueError("history receipt protocol does not bind snapshot capability")


def _verify_supported_capability(capability: GoalRevisionHistoryCapability) -> None:
    if capability.protocol_name != GOAL_REVISION_HISTORY_PROTOCOL:
        raise ValueError("unsupported goal revision history protocol capability")
    if capability.major != GOAL_REVISION_HISTORY_MAJOR:
        raise ValueError("unsupported goal revision history protocol major")
    if capability.minor != GOAL_REVISION_HISTORY_MINOR:
        raise ValueError("unsupported goal revision history protocol minor")
    if capability.features != _FEATURES:
        raise ValueError("unsupported goal revision history capability feature set")


def _verify_entry_authority_semantics(
    entry: GoalRevisionHistoryEntry,
    *,
    ordinal: int,
    previous_contract_digest: str | None,
) -> None:
    if ordinal == 0:
        if entry.trust_label != ROOT_INTEGRITY_CONTRACT_TRUST:
            raise ValueError("goal revision history root trust authority mismatch")
        if not entry.source_refs:
            raise ValueError("goal revision history root requires provenance source refs")
        if entry.evidence_refs:
            raise ValueError("goal revision history root cannot claim revision evidence")
        if entry.transformation_history != _ROOT_TRANSFORMATION_HISTORY:
            raise ValueError("goal revision history root transformation history mismatch")
        return

    if entry.predecessor_digest != previous_contract_digest:
        raise ValueError("goal revision history predecessor contract chain mismatch")

    if entry.trust_label == LEGACY_UNATTESTED_TRUST:
        if any(
            value is not None
            for value in (
                entry.evolution_receipt_id,
                entry.delta_digest,
                entry.freshness_ref,
                entry.confidence_milli,
            )
        ):
            raise ValueError("legacy-unattested revision cannot claim receipt authority")
        if entry.evidence_refs:
            raise ValueError("legacy-unattested revision cannot fabricate evidence")
        if not entry.source_refs:
            raise ValueError("legacy-unattested revision requires contract provenance")
        if entry.transformation_history != _LEGACY_TRANSFORMATION_HISTORY:
            raise ValueError("legacy-unattested revision transformation history mismatch")
        return

    if entry.trust_label not in _RECEIPTED_REVISION_TRUSTS:
        raise ValueError("unsupported goal revision history trust provenance")
    if entry.evolution_receipt_id is None or entry.delta_digest is None:
        raise ValueError("receipted revision trust requires revision receipt authority")
    if not entry.source_refs or not entry.evidence_refs:
        raise ValueError("receipted revision requires source and evidence provenance")
    if entry.freshness_ref is None:
        raise ValueError("receipted revision requires freshness evidence")
    if entry.confidence_milli is None:
        raise ValueError("receipted revision requires bounded confidence")
    if entry.transformation_history != _RECEIPTED_TRANSFORMATION_HISTORY:
        raise ValueError("receipted revision transformation history mismatch")


def verify_goal_revision_history_export(
    export: GoalRevisionHistoryExport,
) -> GoalRevisionHistorySnapshot:
    """Verify public hashes plus the sealed Goal/Design authority contract.

    Content-addressed self-consistency is necessary but not sufficient: a caller
    can otherwise recompute every digest around a forged trust label. This
    verifier therefore also enforces the supported protocol and the semantic
    evidence contract for root, receipted, and legacy-unattested revisions.
    """

    if not isinstance(export, GoalRevisionHistoryExport):
        raise TypeError("expected GoalRevisionHistoryExport")
    snapshot = export.snapshot
    capability = snapshot.capability
    expected_capability = stable_digest(
        {"goal_revision_history_capability": _capability_payload(capability)}
    )
    if capability.digest != expected_capability:
        raise ValueError("goal revision history capability digest mismatch")
    _verify_supported_capability(capability)

    if not snapshot.entries:
        raise ValueError("goal revision history snapshot requires entries")
    if len(snapshot.entries) > _MAX_HISTORY_ENTRIES:
        raise ValueError("goal revision history snapshot exceeds bounded entry count")
    if len({entry.contract_digest for entry in snapshot.entries}) != len(snapshot.entries):
        raise ValueError("goal revision history contains duplicate contract identity")

    previous_entry_digest: str | None = None
    previous_contract_digest: str | None = None
    for ordinal, entry in enumerate(snapshot.entries):
        expected_entry = stable_digest({"goal_revision_history_entry": _entry_payload(entry)})
        if entry.entry_digest != expected_entry:
            raise ValueError("goal revision history entry digest mismatch")
        if entry.goal_id != snapshot.goal_id:
            raise ValueError("goal revision history entry goal mismatch")
        if entry.ordinal != ordinal:
            raise ValueError("goal revision history ordinal mismatch")
        if entry.previous_entry_digest != previous_entry_digest:
            raise ValueError("goal revision history chain link mismatch")
        _verify_entry_authority_semantics(
            entry,
            ordinal=ordinal,
            previous_contract_digest=previous_contract_digest,
        )
        previous_entry_digest = entry.entry_digest
        previous_contract_digest = entry.contract_digest

    expected_history = stable_digest(
        {"goal_revision_history_snapshot": _snapshot_payload(snapshot)}
    )
    if snapshot.history_digest != expected_history:
        raise ValueError("goal revision history snapshot digest mismatch")
    if snapshot.entries[-1].contract_digest != snapshot.current_contract_digest:
        raise ValueError("goal revision history current head mismatch")

    receipt = export.receipt
    expected_receipt = stable_digest(
        {"goal_revision_history_receipt": _receipt_payload(receipt)}
    )
    if receipt.receipt_id != expected_receipt:
        raise ValueError("goal revision history receipt identity mismatch")
    if receipt.goal_id != snapshot.goal_id:
        raise ValueError("goal revision history receipt goal mismatch")
    if receipt.history_digest != snapshot.history_digest:
        raise ValueError("goal revision history receipt snapshot mismatch")
    if receipt.current_contract_digest != snapshot.current_contract_digest:
        raise ValueError("goal revision history receipt current head mismatch")
    if receipt.entry_count != len(snapshot.entries):
        raise ValueError("goal revision history receipt entry count mismatch")
    if (
        receipt.protocol_major != capability.major
        or receipt.protocol_minor != capability.minor
    ):
        raise ValueError("goal revision history receipt capability mismatch")
    return snapshot


class GoalRevisionHistoryCompiler:
    """Pure deterministic projection of authenticated Goal Integrity history."""

    def negotiate(
        self,
        *,
        protocol_major: int = GOAL_REVISION_HISTORY_MAJOR,
        minimum_minor: int = 0,
    ) -> GoalRevisionHistoryCapability:
        major = int(protocol_major)
        minor = int(minimum_minor)
        if major != GOAL_REVISION_HISTORY_MAJOR:
            raise ValueError(
                f"unsupported goal revision history protocol major {major}"
            )
        if minor < 0 or minor > GOAL_REVISION_HISTORY_MINOR:
            raise ValueError(
                f"unsupported goal revision history minimum minor {minor}"
            )
        return GoalRevisionHistoryCapability()

    def compile(
        self,
        *,
        goal_id: str,
        current_contract_digest: str,
        contracts: Mapping[str, GoalIntegrityContract],
        predecessors: Mapping[str, str | None],
        evolution_receipts: Mapping[str, GoalIntegrityEvolutionReceipt],
        trust_label_resolver: Callable[[str], str],
        protocol_major: int = GOAL_REVISION_HISTORY_MAJOR,
        minimum_minor: int = 0,
    ) -> GoalRevisionHistoryExport:
        goal_id = _text("goal_id", goal_id, limit=_MAX_REF)
        current_contract_digest = _text(
            "current_contract_digest", current_contract_digest, limit=_MAX_REF
        )
        capability = self.negotiate(
            protocol_major=protocol_major,
            minimum_minor=minimum_minor,
        )
        contract_map = dict(contracts)
        predecessor_map = dict(predecessors)
        receipt_map = dict(evolution_receipts)

        chain_descending: list[str] = []
        seen: set[str] = set()
        digest = current_contract_digest
        while True:
            if digest in seen:
                raise ValueError("goal revision history predecessor cycle detected")
            seen.add(digest)
            if len(seen) > _MAX_HISTORY_ENTRIES:
                raise ValueError("goal revision history exceeds bounded entry count")
            contract = contract_map.get(digest)
            if not isinstance(contract, GoalIntegrityContract):
                raise ValueError("goal revision history references unknown contract")
            if contract.digest != digest:
                raise ValueError("goal revision history contract key/digest mismatch")
            if contract.goal_id != goal_id:
                raise ValueError("goal revision history contract crosses goal authority")
            if digest not in predecessor_map:
                raise ValueError("goal revision history predecessor mapping is incomplete")
            chain_descending.append(digest)
            predecessor = predecessor_map[digest]
            if predecessor is None:
                break
            digest = _text("predecessor_digest", predecessor, limit=_MAX_REF)

        chain = tuple(reversed(chain_descending))
        same_goal_contracts: set[str] = set()
        for key, contract in contract_map.items():
            if not isinstance(contract, GoalIntegrityContract):
                raise ValueError("goal revision history contract mapping is malformed")
            if contract.goal_id == goal_id:
                key_text = _text("contract_digest", key, limit=_MAX_REF)
                if contract.digest != key_text:
                    raise ValueError("goal revision history contract mapping rebinds identity")
                same_goal_contracts.add(key_text)
        if same_goal_contracts != set(chain):
            raise ValueError(
                "goal revision history current head does not cover one linear goal chain"
            )

        for key, receipt in receipt_map.items():
            if not isinstance(receipt, GoalIntegrityEvolutionReceipt):
                raise ValueError("goal revision history evolution receipt mapping is malformed")
            if receipt.goal_id == goal_id and str(key).strip() not in set(chain):
                raise ValueError("goal revision history contains orphan evolution receipt")
        if chain[0] in receipt_map:
            raise ValueError("goal revision history root cannot have an evolution receipt")

        entries: list[GoalRevisionHistoryEntry] = []
        for ordinal, contract_digest in enumerate(chain):
            contract = contract_map[contract_digest]
            previous_entry_digest = entries[-1].entry_digest if entries else None
            if ordinal == 0:
                entry = GoalRevisionHistoryEntry(
                    goal_id=goal_id,
                    ordinal=0,
                    contract_digest=contract_digest,
                    trust_label=ROOT_INTEGRITY_CONTRACT_TRUST,
                    source_refs=_contract_provenance(contract),
                    evidence_refs=(),
                    transformation_history=_ROOT_TRANSFORMATION_HISTORY,
                )
                entries.append(entry)
                continue

            predecessor_digest = chain[ordinal - 1]
            predecessor = contract_map[predecessor_digest]
            receipt = receipt_map.get(contract_digest)
            try:
                trust_label = _text(
                    "trust_label",
                    trust_label_resolver(contract_digest),
                    limit=_MAX_REF,
                )
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError(
                    "goal revision history trust provenance is unavailable"
                ) from exc

            if receipt is None:
                if trust_label != LEGACY_UNATTESTED_TRUST:
                    raise ValueError(
                        "receiptless goal revision cannot claim verified trust provenance"
                    )
                entry = GoalRevisionHistoryEntry(
                    goal_id=goal_id,
                    ordinal=ordinal,
                    contract_digest=contract_digest,
                    trust_label=trust_label,
                    predecessor_digest=predecessor_digest,
                    source_refs=_contract_provenance(contract),
                    evidence_refs=(),
                    transformation_history=_LEGACY_TRANSFORMATION_HISTORY,
                    previous_entry_digest=previous_entry_digest,
                )
            else:
                if trust_label == LEGACY_UNATTESTED_TRUST:
                    raise ValueError(
                        "explicit goal revision receipt cannot be labeled legacy-unattested"
                    )
                delta = verify_goal_integrity_evolution_receipt(
                    receipt,
                    predecessor=predecessor,
                    successor=contract,
                )
                entry = GoalRevisionHistoryEntry(
                    goal_id=goal_id,
                    ordinal=ordinal,
                    contract_digest=contract_digest,
                    trust_label=trust_label,
                    predecessor_digest=predecessor_digest,
                    evolution_receipt_id=receipt.receipt_id,
                    delta_digest=delta.digest,
                    source_refs=receipt.source_refs,
                    evidence_refs=receipt.evidence_refs,
                    freshness_ref=receipt.freshness_ref,
                    confidence_milli=receipt.confidence_milli,
                    transformation_history=_RECEIPTED_TRANSFORMATION_HISTORY,
                    previous_entry_digest=previous_entry_digest,
                )
            entries.append(entry)

        snapshot = GoalRevisionHistorySnapshot(
            capability=capability,
            goal_id=goal_id,
            current_contract_digest=current_contract_digest,
            entries=tuple(entries),
        )
        receipt = GoalRevisionHistoryReceipt(
            protocol_major=capability.major,
            protocol_minor=capability.minor,
            goal_id=goal_id,
            history_digest=snapshot.history_digest,
            current_contract_digest=current_contract_digest,
            entry_count=len(snapshot.entries),
        )
        export = GoalRevisionHistoryExport(snapshot=snapshot, receipt=receipt)
        verify_goal_revision_history_export(export)
        return export


__all__ = [
    "GOAL_REVISION_HISTORY_MAJOR",
    "GOAL_REVISION_HISTORY_MINOR",
    "GOAL_REVISION_HISTORY_PROTOCOL",
    "ROOT_INTEGRITY_CONTRACT_TRUST",
    "GoalRevisionHistoryCapability",
    "GoalRevisionHistoryCompiler",
    "GoalRevisionHistoryEntry",
    "GoalRevisionHistoryExport",
    "GoalRevisionHistoryReceipt",
    "GoalRevisionHistorySnapshot",
    "verify_goal_revision_history_export",
]
