from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest


LIVE_FABRIC_PROTOCOL = "external-core-live-fabric-v1"


def _explicit(value: object, label: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an explicit string")
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


def _validate_canonical(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite number is not canonical at {path}")
        return
    if isinstance(value, list) or isinstance(value, tuple):
        for index, item in enumerate(value):
            _validate_canonical(item, f"{path}[{index}]")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"canonical object key must be a non-empty string at {path}")
            _validate_canonical(item, f"{path}.{key}")
        return
    raise ValueError(f"unsupported canonical value at {path}: {type(value).__name__}")


def _frontier_digest(domain: str, rows: Sequence[Mapping[str, Any]]) -> str:
    normalized: list[dict[str, Any]] = []
    row_digests: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError(f"{domain} frontier entries must be objects")
        state = dict(row)
        _validate_canonical(state)
        digest = canonical_digest(state)
        if digest in row_digests:
            raise ValueError(f"duplicate {domain} frontier entry")
        row_digests.add(digest)
        normalized.append(state)
    ordered = sorted(normalized, key=lambda state: canonical_digest(state))
    return f"{domain}-frontier-v1-" + canonical_digest(
        {"protocol": f"{domain}-frontier-v1", "entries": ordered}
    )


def handoff_frontier_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    return _frontier_digest("handoff", rows)


def work_trace_frontier_digest(rows: Sequence[Mapping[str, Any]]) -> str:
    return _frontier_digest("work-trace", rows)


def source_state_frontier_digest(source_states: Mapping[str, str]) -> str:
    normalized: dict[str, str] = {}
    for source, digest in source_states.items():
        key = _explicit(source, "source state key")
        if key in normalized:
            raise ValueError("duplicate source state key")
        normalized[key] = _explicit(digest, "source state digest")
    payload = {
        "protocol": "source-state-frontier-v1",
        "sources": {key: normalized[key] for key in sorted(normalized)},
    }
    return "source-state-frontier-v1-" + canonical_digest(payload)


def empty_live_frontiers() -> tuple[str, str, str]:
    return handoff_frontier_digest(()), work_trace_frontier_digest(()), source_state_frontier_digest({})


def _normalize_component_versions(values: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for component_id, raw_version in values.items():
        identity = _explicit(component_id, "component identity")
        if identity in seen:
            raise ValueError("duplicate component identity in live fabric snapshot")
        seen.add(identity)
        if not isinstance(raw_version, str):
            raise ValueError("component version must be an explicit string")
        version = _explicit(raw_version, "component version")
        rows.append((identity, version))
    return tuple(sorted(rows))


@dataclass(frozen=True, slots=True)
class LiveExternalCoreSnapshot:
    registry_digest: str
    authority_graph_digest: str
    artifact_graph_digest: str
    handoff_frontier_digest: str
    work_trace_frontier_digest: str
    source_state_frontier_digest: str
    component_versions: tuple[tuple[str, str], ...]
    snapshot_id: str

    def payload(self) -> dict[str, Any]:
        return {
            "protocol": LIVE_FABRIC_PROTOCOL,
            "registry_digest": self.registry_digest,
            "authority_graph_digest": self.authority_graph_digest,
            "artifact_graph_digest": self.artifact_graph_digest,
            "handoff_frontier_digest": self.handoff_frontier_digest,
            "work_trace_frontier_digest": self.work_trace_frontier_digest,
            "source_state_frontier_digest": self.source_state_frontier_digest,
            "component_versions": [[component_id, version] for component_id, version in self.component_versions],
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "snapshot_id": self.snapshot_id}

    @classmethod
    def create(
        cls,
        *,
        registry_digest: str,
        authority_graph_digest: str,
        artifact_graph_digest: str,
        handoff_frontier_digest: str,
        work_trace_frontier_digest: str,
        source_state_frontier_digest: str,
        component_versions: Mapping[str, object],
    ) -> "LiveExternalCoreSnapshot":
        payload = {
            "protocol": LIVE_FABRIC_PROTOCOL,
            "registry_digest": _explicit(registry_digest, "registry digest"),
            "authority_graph_digest": _explicit(authority_graph_digest, "authority graph digest"),
            "artifact_graph_digest": _explicit(artifact_graph_digest, "artifact graph digest"),
            "handoff_frontier_digest": _explicit(handoff_frontier_digest, "handoff frontier digest"),
            "work_trace_frontier_digest": _explicit(work_trace_frontier_digest, "work trace frontier digest"),
            "source_state_frontier_digest": _explicit(source_state_frontier_digest, "source state frontier digest"),
            "component_versions": [list(row) for row in _normalize_component_versions(component_versions)],
        }
        return cls(
            registry_digest=payload["registry_digest"],
            authority_graph_digest=payload["authority_graph_digest"],
            artifact_graph_digest=payload["artifact_graph_digest"],
            handoff_frontier_digest=payload["handoff_frontier_digest"],
            work_trace_frontier_digest=payload["work_trace_frontier_digest"],
            source_state_frontier_digest=payload["source_state_frontier_digest"],
            component_versions=tuple((row[0], row[1]) for row in payload["component_versions"]),
            snapshot_id="live-fabric-v1-" + canonical_digest(payload),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "LiveExternalCoreSnapshot":
        if str(state.get("protocol", "")) != LIVE_FABRIC_PROTOCOL:
            raise ValueError("live fabric snapshot protocol mismatch")
        raw_versions = state.get("component_versions")
        if not isinstance(raw_versions, list):
            raise ValueError("live fabric component_versions must be an array")
        pairs: list[tuple[str, str]] = []
        seen: set[str] = set()
        for row in raw_versions:
            if not isinstance(row, list) or len(row) != 2:
                raise ValueError("live fabric component version entry must be [component_id, version]")
            if isinstance(row[1], bool):
                raise ValueError("component version must be an explicit string")
            component_id = _explicit(row[0], "component identity")
            version = _explicit(row[1], "component version")
            if component_id in seen:
                raise ValueError("duplicate component identity in live fabric snapshot")
            seen.add(component_id)
            pairs.append((component_id, version))
        expected = cls.create(
            registry_digest=str(state.get("registry_digest", "")),
            authority_graph_digest=str(state.get("authority_graph_digest", "")),
            artifact_graph_digest=str(state.get("artifact_graph_digest", "")),
            handoff_frontier_digest=str(state.get("handoff_frontier_digest", "")),
            work_trace_frontier_digest=str(state.get("work_trace_frontier_digest", "")),
            source_state_frontier_digest=str(state.get("source_state_frontier_digest", "")),
            component_versions=dict(pairs),
        )
        if str(state.get("snapshot_id", "")) != expected.snapshot_id:
            raise ValueError("live fabric snapshot digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("live fabric snapshot state is non-canonical or semantically drifted")
        return expected


class LiveRestoreDisposition(str, Enum):
    CURRENT = "CURRENT"
    REQUIRES_REVALIDATION = "REQUIRES_REVALIDATION"
    QUARANTINED = "QUARANTINED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class LiveRestoreAssessment:
    disposition: LiveRestoreDisposition
    reasons: tuple[str, ...]

    @property
    def authoritative(self) -> bool:
        return self.disposition is LiveRestoreDisposition.CURRENT

    def to_state(self) -> dict[str, Any]:
        return {
            "disposition": self.disposition.value,
            "authoritative": self.authoritative,
            "reasons": list(self.reasons),
        }


def assess_live_restore(
    snapshot: LiveExternalCoreSnapshot,
    *,
    current_registry_digest: str | None,
    current_authority_graph_digest: str | None,
    current_artifact_graph_digest: str | None,
    current_handoff_frontier_digest: str | None,
    current_work_trace_frontier_digest: str | None,
    current_source_state_frontier_digest: str | None,
    current_component_versions: Mapping[str, object] | None,
) -> LiveRestoreAssessment:
    current_values = (
        ("registry", current_registry_digest),
        ("authority-graph", current_authority_graph_digest),
        ("artifact-graph", current_artifact_graph_digest),
        ("handoff-frontier", current_handoff_frontier_digest),
        ("work-trace-frontier", current_work_trace_frontier_digest),
        ("source-state-frontier", current_source_state_frontier_digest),
    )
    missing = [f"missing-current-{label}" for label, value in current_values if value is None]
    if current_component_versions is None:
        missing.append("missing-current-component-versions")
    if missing:
        return LiveRestoreAssessment(LiveRestoreDisposition.UNKNOWN, tuple(sorted(missing)))

    reasons: list[str] = []
    comparisons = (
        ("registry-drift", snapshot.registry_digest, current_registry_digest),
        ("authority-graph-drift", snapshot.authority_graph_digest, current_authority_graph_digest),
        ("artifact-graph-drift", snapshot.artifact_graph_digest, current_artifact_graph_digest),
        ("handoff-frontier-drift", snapshot.handoff_frontier_digest, current_handoff_frontier_digest),
        ("work-trace-frontier-drift", snapshot.work_trace_frontier_digest, current_work_trace_frontier_digest),
        ("source-state-frontier-drift", snapshot.source_state_frontier_digest, current_source_state_frontier_digest),
    )
    for reason, historical, current in comparisons:
        if historical != current:
            reasons.append(reason)

    historical_versions = dict(snapshot.component_versions)
    current_versions = dict(_normalize_component_versions(current_component_versions or {}))
    for component_id in sorted(set(historical_versions) | set(current_versions)):
        historical = historical_versions.get(component_id)
        current = current_versions.get(component_id)
        if historical is None:
            reasons.append(f"unexpected-component:{component_id}")
        elif current is None:
            reasons.append(f"missing-component:{component_id}")
        elif historical != current:
            reasons.append(f"version-drift:{component_id}:{historical}->{current}")

    if reasons:
        return LiveRestoreAssessment(
            LiveRestoreDisposition.REQUIRES_REVALIDATION,
            tuple(sorted(set(reasons))),
        )
    return LiveRestoreAssessment(LiveRestoreDisposition.CURRENT, ())


def assess_live_restore_state(
    state: Mapping[str, Any],
    **current_state: Any,
) -> LiveRestoreAssessment:
    try:
        snapshot = LiveExternalCoreSnapshot.from_state(state)
    except (KeyError, TypeError, ValueError):
        return LiveRestoreAssessment(LiveRestoreDisposition.QUARANTINED, ("invalid-snapshot",))
    return assess_live_restore(snapshot, **current_state)
