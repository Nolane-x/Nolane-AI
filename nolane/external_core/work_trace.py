from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest


WORK_TRACE_PROTOCOL = "cognitive-work-trace-v1"


class TraceNodeStatus(str, Enum):
    INFORMATIVE = "informative"
    PROPOSED = "proposed"
    VERIFIED = "verified"
    ASSURED = "assured"
    AUTHORIZED_OBSERVED = "authorized_observed"
    EXECUTION_RESULT = "execution_result"
    LEARNING_RESULT = "learning_result"
    NEGATIVE = "negative"
    BLOCKED = "blocked"
    ABORTED = "aborted"


@dataclass(frozen=True, slots=True)
class TraceNode:
    node_id: str
    trace_id: str
    component_id: str
    subject_id: str
    subject_digest: str
    status: TraceNodeStatus
    predecessor_node_ids: tuple[str, ...]
    handoff_id: str | None
    evidence_refs: tuple[str, ...]
    limitations: tuple[str, ...]
    digest: str

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "protocol": WORK_TRACE_PROTOCOL,
            "trace_id": self.trace_id,
            "component_id": self.component_id,
            "subject_id": self.subject_id,
            "subject_digest": self.subject_digest,
            "status": self.status.value,
            "predecessor_node_ids": list(self.predecessor_node_ids),
            "handoff_id": self.handoff_id,
            "evidence_refs": list(self.evidence_refs),
            "limitations": list(self.limitations),
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "trace_id": self.trace_id,
            "component_id": self.component_id,
            "subject_id": self.subject_id,
            "subject_digest": self.subject_digest,
            "status": self.status.value,
            "predecessor_node_ids": list(self.predecessor_node_ids),
            "handoff_id": self.handoff_id,
            "evidence_refs": list(self.evidence_refs),
            "limitations": list(self.limitations),
            "digest": self.digest,
        }

    @classmethod
    def create(
        cls,
        *,
        trace_id: str,
        component_id: str,
        subject_id: str,
        subject_digest: str,
        status: TraceNodeStatus | str,
        predecessor_node_ids: tuple[str, ...],
        handoff_id: str | None,
        evidence_refs: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> "TraceNode":
        predecessors = _unique_explicit(predecessor_node_ids, "trace predecessor node id")
        evidence = _unique_explicit(evidence_refs, "trace evidence ref")
        limitation_rows = _unique_explicit(limitations, "trace limitation")
        handoff = None if handoff_id is None else _explicit(handoff_id, "trace handoff id")
        row = cls(
            node_id="",
            trace_id=_explicit(trace_id, "trace id"),
            component_id=_explicit(component_id, "trace component id"),
            subject_id=_explicit(subject_id, "trace subject id"),
            subject_digest=_explicit(subject_digest, "trace subject digest"),
            status=TraceNodeStatus(status),
            predecessor_node_ids=predecessors,
            handoff_id=handoff,
            evidence_refs=evidence,
            limitations=limitation_rows,
            digest="",
        )
        digest = canonical_digest(row.semantic_payload())
        return cls(
            node_id="trace-node-" + digest[:24],
            trace_id=row.trace_id,
            component_id=row.component_id,
            subject_id=row.subject_id,
            subject_digest=row.subject_digest,
            status=row.status,
            predecessor_node_ids=row.predecessor_node_ids,
            handoff_id=row.handoff_id,
            evidence_refs=row.evidence_refs,
            limitations=row.limitations,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TraceNode":
        expected = cls.create(
            trace_id=str(state["trace_id"]),
            component_id=str(state["component_id"]),
            subject_id=str(state["subject_id"]),
            subject_digest=str(state["subject_digest"]),
            status=str(state["status"]),
            predecessor_node_ids=tuple(str(x) for x in state.get("predecessor_node_ids", ())),
            handoff_id=None if state.get("handoff_id") is None else str(state["handoff_id"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
            limitations=tuple(str(x) for x in state.get("limitations", ())),
        )
        if str(state.get("node_id", "")) != expected.node_id:
            raise ValueError("trace node identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("trace node digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("trace node state is non-canonical or semantically drifted")
        return expected


@dataclass(frozen=True, slots=True)
class TraceSupersessionReceipt:
    receipt_id: str
    trace_id: str
    predecessor_node_id: str
    successor_node_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    digest: str

    def semantic_payload(self) -> dict[str, Any]:
        return {
            "protocol": WORK_TRACE_PROTOCOL,
            "trace_id": self.trace_id,
            "predecessor_node_id": self.predecessor_node_id,
            "successor_node_id": self.successor_node_id,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
        }

    def to_state(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "trace_id": self.trace_id,
            "predecessor_node_id": self.predecessor_node_id,
            "successor_node_id": self.successor_node_id,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "digest": self.digest,
        }

    @classmethod
    def create(
        cls,
        *,
        trace_id: str,
        predecessor_node_id: str,
        successor_node_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> "TraceSupersessionReceipt":
        predecessor = _explicit(predecessor_node_id, "supersession predecessor node id")
        successor = _explicit(successor_node_id, "supersession successor node id")
        if predecessor == successor:
            raise ValueError("trace node cannot supersede itself")
        evidence = _unique_explicit(evidence_refs, "supersession evidence ref")
        row = cls(
            receipt_id="",
            trace_id=_explicit(trace_id, "trace id"),
            predecessor_node_id=predecessor,
            successor_node_id=successor,
            reason=_explicit(reason, "supersession reason"),
            evidence_refs=evidence,
            digest="",
        )
        digest = canonical_digest(row.semantic_payload())
        return cls(
            receipt_id="trace-supersession-" + digest[:24],
            trace_id=row.trace_id,
            predecessor_node_id=row.predecessor_node_id,
            successor_node_id=row.successor_node_id,
            reason=row.reason,
            evidence_refs=row.evidence_refs,
            digest=digest,
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "TraceSupersessionReceipt":
        expected = cls.create(
            trace_id=str(state["trace_id"]),
            predecessor_node_id=str(state["predecessor_node_id"]),
            successor_node_id=str(state["successor_node_id"]),
            reason=str(state["reason"]),
            evidence_refs=tuple(str(x) for x in state.get("evidence_refs", ())),
        )
        if str(state.get("receipt_id", "")) != expected.receipt_id:
            raise ValueError("trace supersession identity mismatch")
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("trace supersession digest mismatch")
        if dict(state) != expected.to_state():
            raise ValueError("trace supersession state is non-canonical")
        return expected


@dataclass(frozen=True, slots=True)
class TraceDiagnostic:
    code: str
    node_ids: tuple[str, ...]
    detail: str


class CognitiveWorkTrace:
    """Append-only descriptive provenance DAG.

    The trace deliberately exposes no authorize/promote/execute API. It records
    externally produced work lineage and supersession receipts only.
    """

    def __init__(self, trace_id: str) -> None:
        self.trace_id = _explicit(trace_id, "trace id")
        self._nodes: dict[str, TraceNode] = {}
        self._supersessions: dict[str, TraceSupersessionReceipt] = {}

    @property
    def digest(self) -> str:
        return canonical_digest(self._payload())

    def nodes(self) -> tuple[TraceNode, ...]:
        return tuple(self._nodes[key] for key in sorted(self._nodes))

    def node(self, node_id: str) -> TraceNode:
        try:
            return self._nodes[str(node_id)]
        except KeyError as exc:
            raise KeyError(f"unknown trace node: {node_id}") from exc

    def append_node(
        self,
        *,
        component_id: str,
        subject_id: str,
        subject_digest: str,
        status: TraceNodeStatus | str,
        predecessor_node_ids: tuple[str, ...],
        handoff_id: str | None = None,
        evidence_refs: tuple[str, ...] = (),
        limitations: tuple[str, ...] = (),
    ) -> TraceNode:
        row = TraceNode.create(
            trace_id=self.trace_id,
            component_id=component_id,
            subject_id=subject_id,
            subject_digest=subject_digest,
            status=status,
            predecessor_node_ids=predecessor_node_ids,
            handoff_id=handoff_id,
            evidence_refs=evidence_refs,
            limitations=limitations,
        )
        missing = tuple(predecessor for predecessor in row.predecessor_node_ids if predecessor not in self._nodes)
        if missing:
            raise KeyError("trace predecessor missing: " + ",".join(missing))
        existing = self._nodes.get(row.node_id)
        if existing is not None:
            if existing != row:
                raise ValueError("trace node id cannot be rebound")
            return existing
        self._nodes[row.node_id] = row
        return row

    def supersede(
        self,
        predecessor_node_id: str,
        *,
        successor_node_id: str,
        reason: str,
        evidence_refs: tuple[str, ...],
    ) -> TraceSupersessionReceipt:
        predecessor = self.node(predecessor_node_id)
        successor = self.node(successor_node_id)
        receipt = TraceSupersessionReceipt.create(
            trace_id=self.trace_id,
            predecessor_node_id=predecessor.node_id,
            successor_node_id=successor.node_id,
            reason=reason,
            evidence_refs=evidence_refs,
        )
        existing = self._supersessions.get(predecessor.node_id)
        if existing is not None:
            if existing != receipt:
                raise ValueError("trace predecessor already superseded by a different receipt")
            return existing
        self._supersessions[predecessor.node_id] = receipt
        return receipt

    def supersession(self, predecessor_node_id: str) -> TraceSupersessionReceipt | None:
        return self._supersessions.get(str(predecessor_node_id))

    def diagnostics(self, *, known_handoff_ids: tuple[str, ...] | None = None) -> tuple[TraceDiagnostic, ...]:
        findings: list[TraceDiagnostic] = []
        for node in self.nodes():
            missing = tuple(predecessor for predecessor in node.predecessor_node_ids if predecessor not in self._nodes)
            if missing:
                findings.append(
                    TraceDiagnostic(
                        "MISSING_PREDECESSOR_NODE",
                        (node.node_id,),
                        "missing predecessor trace node(s): " + ",".join(missing),
                    )
                )
            if known_handoff_ids is not None and node.handoff_id is not None:
                if node.handoff_id not in set(known_handoff_ids):
                    findings.append(
                        TraceDiagnostic(
                            "MISSING_HANDOFF_REFERENCE",
                            (node.node_id,),
                            f"referenced handoff is not present: {node.handoff_id}",
                        )
                    )
            if node.status in {TraceNodeStatus.NEGATIVE, TraceNodeStatus.ABORTED, TraceNodeStatus.BLOCKED} and not node.evidence_refs:
                findings.append(
                    TraceDiagnostic(
                        "NEGATIVE_LINEAGE_WITHOUT_EVIDENCE",
                        (node.node_id,),
                        "negative/aborted/blocked trace node has no retained evidence reference",
                    )
                )
        return tuple(sorted(findings, key=lambda row: (row.code, row.node_ids, row.detail)))

    def _payload(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "protocol": WORK_TRACE_PROTOCOL,
            "nodes": [row.to_state() for row in self.nodes()],
            "supersessions": [
                self._supersessions[key].to_state() for key in sorted(self._supersessions)
            ],
        }

    def to_state(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "CognitiveWorkTrace":
        trace = cls(str(state["trace_id"]))
        protocol = str(state.get("protocol", ""))
        if protocol != WORK_TRACE_PROTOCOL:
            raise ValueError("unsupported cognitive work trace protocol")

        raw_nodes = tuple(TraceNode.from_state(value) for value in state.get("nodes", ()))
        if any(row.trace_id != trace.trace_id for row in raw_nodes):
            raise ValueError("trace node belongs to a different trace")
        if len({row.node_id for row in raw_nodes}) != len(raw_nodes):
            raise ValueError("duplicate trace node id in serialized state")
        trace._nodes = {row.node_id: row for row in raw_nodes}
        for row in raw_nodes:
            missing = tuple(predecessor for predecessor in row.predecessor_node_ids if predecessor not in trace._nodes)
            if missing:
                raise ValueError("trace contains missing predecessor link")
        if _has_cycle(trace._nodes):
            raise ValueError("trace predecessor graph contains a cycle")

        receipts = tuple(
            TraceSupersessionReceipt.from_state(value) for value in state.get("supersessions", ())
        )
        if any(row.trace_id != trace.trace_id for row in receipts):
            raise ValueError("trace supersession belongs to a different trace")
        for receipt in receipts:
            if receipt.predecessor_node_id not in trace._nodes or receipt.successor_node_id not in trace._nodes:
                raise ValueError("trace supersession references missing node")
            existing = trace._supersessions.get(receipt.predecessor_node_id)
            if existing is not None and existing != receipt:
                raise ValueError("multiple supersession receipts for one trace predecessor")
            trace._supersessions[receipt.predecessor_node_id] = receipt

        if str(state.get("digest", "")) != trace.digest:
            raise ValueError("cognitive work trace digest mismatch")
        if dict(state) != trace.to_state():
            raise ValueError("cognitive work trace state is non-canonical")
        return trace


def _has_cycle(nodes: Mapping[str, TraceNode]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in visiting:
            return True
        if node_id in visited:
            return False
        visiting.add(node_id)
        for predecessor in nodes[node_id].predecessor_node_ids:
            if visit(predecessor):
                return True
        visiting.remove(node_id)
        visited.add(node_id)
        return False

    return any(visit(node_id) for node_id in sorted(nodes) if node_id not in visited)


def _unique_explicit(values: tuple[str, ...], label: str) -> tuple[str, ...]:
    rows = tuple(_explicit(value, label) for value in values)
    if len(set(rows)) != len(rows):
        raise ValueError(f"duplicate {label}")
    return tuple(sorted(rows))


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


__all__ = (
    "WORK_TRACE_PROTOCOL",
    "CognitiveWorkTrace",
    "TraceDiagnostic",
    "TraceNode",
    "TraceNodeStatus",
    "TraceSupersessionReceipt",
)
