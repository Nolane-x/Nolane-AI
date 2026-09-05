from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.component_contracts import ExternalComponentManifest


class AuthorityRelation(str, Enum):
    PROPOSES_TO = "proposes_to"
    EVIDENCE_FOR = "evidence_for"
    VERIFIES = "verifies"
    ASSURES = "assures"
    AUTHORIZES_INPUT_TO = "authorizes_input_to"
    EXECUTES_FOR = "executes_for"
    OBSERVES = "observes"
    LEARNING_INPUT_TO = "learning_input_to"
    PUBLISHES_ARTIFACT_TO = "publishes_artifact_to"
    REVOKES_DESCENDANTS_OF = "revokes_descendants_of"


_RELATION_AUTHORITY = {
    AuthorityRelation.VERIFIES: "verify",
    AuthorityRelation.ASSURES: "assure",
    AuthorityRelation.AUTHORIZES_INPUT_TO: "authorize",
    AuthorityRelation.EXECUTES_FOR: "execute",
    AuthorityRelation.LEARNING_INPUT_TO: "learn",
    AuthorityRelation.REVOKES_DESCENDANTS_OF: "revoke",
}

_ESCALATING_RELATIONS = frozenset(
    {
        AuthorityRelation.VERIFIES,
        AuthorityRelation.ASSURES,
        AuthorityRelation.AUTHORIZES_INPUT_TO,
        AuthorityRelation.EXECUTES_FOR,
        AuthorityRelation.REVOKES_DESCENDANTS_OF,
    }
)


@dataclass(frozen=True, slots=True)
class AuthorityEdge:
    source_component_id: str
    target_component_id: str
    relation: AuthorityRelation
    contract_kind: str
    digest: str

    def payload(self) -> dict[str, Any]:
        return {
            "source_component_id": self.source_component_id,
            "target_component_id": self.target_component_id,
            "relation": self.relation.value,
            "contract_kind": self.contract_kind,
        }

    def to_state(self) -> dict[str, Any]:
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def create(
        cls,
        *,
        source_component_id: str,
        target_component_id: str,
        relation: AuthorityRelation | str,
        contract_kind: str,
    ) -> "AuthorityEdge":
        payload = {
            "source_component_id": _explicit(source_component_id, "authority edge source"),
            "target_component_id": _explicit(target_component_id, "authority edge target"),
            "relation": AuthorityRelation(relation).value,
            "contract_kind": _explicit(contract_kind, "authority edge contract kind"),
        }
        return cls(
            source_component_id=payload["source_component_id"],
            target_component_id=payload["target_component_id"],
            relation=AuthorityRelation(payload["relation"]),
            contract_kind=payload["contract_kind"],
            digest=canonical_digest(payload),
        )

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "AuthorityEdge":
        expected = cls.create(
            source_component_id=str(state["source_component_id"]),
            target_component_id=str(state["target_component_id"]),
            relation=str(state["relation"]),
            contract_kind=str(state["contract_kind"]),
        )
        if str(state.get("digest", "")) != expected.digest:
            raise ValueError("authority edge digest mismatch")
        return expected


@dataclass(frozen=True, slots=True)
class AuthorityGraphFinding:
    code: str
    component_ids: tuple[str, ...]
    subject: str
    detail: str

    def payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "component_ids": list(self.component_ids),
            "subject": self.subject,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class AuthorityGraphValidationReport:
    findings: tuple[AuthorityGraphFinding, ...]
    digest: str

    @property
    def clean(self) -> bool:
        return not self.findings


class ExternalAuthorityGraph:
    """Machine-checkable structural authority map across External Core families.

    The graph is purely constraining/descriptive. It never mints a runtime
    authorization or upgrades a handoff's authority class.
    """

    def __init__(
        self,
        manifests: tuple[ExternalComponentManifest, ...],
        edges: tuple[AuthorityEdge, ...],
    ) -> None:
        ordered_manifests = tuple(sorted(manifests, key=lambda row: row.component_id))
        if len({row.component_id for row in ordered_manifests}) != len(ordered_manifests):
            raise ValueError("duplicate component id in authority graph")
        ordered_edges = tuple(
            sorted(
                edges,
                key=lambda row: (
                    row.source_component_id,
                    row.target_component_id,
                    row.relation.value,
                    row.contract_kind,
                ),
            )
        )
        if len({row.digest for row in ordered_edges}) != len(ordered_edges):
            raise ValueError("duplicate authority edge")
        self._manifests = ordered_manifests
        self._by_id = {row.component_id: row for row in ordered_manifests}
        self._edges = ordered_edges

    @property
    def manifests(self) -> tuple[ExternalComponentManifest, ...]:
        return self._manifests

    @property
    def edges(self) -> tuple[AuthorityEdge, ...]:
        return self._edges

    @property
    def digest(self) -> str:
        return canonical_digest(self._payload())

    def manifest(self, component_id: str) -> ExternalComponentManifest:
        try:
            return self._by_id[str(component_id)]
        except KeyError as exc:
            raise KeyError(f"unknown External Core component manifest: {component_id}") from exc

    def findings(self) -> tuple[AuthorityGraphFinding, ...]:
        rows: list[AuthorityGraphFinding] = []
        rows.extend(self._duplicate_writer_findings())

        for edge in self._edges:
            source = self._by_id.get(edge.source_component_id)
            target = self._by_id.get(edge.target_component_id)
            if source is None or target is None:
                missing = tuple(
                    component_id
                    for component_id, manifest in (
                        (edge.source_component_id, source),
                        (edge.target_component_id, target),
                    )
                    if manifest is None
                )
                rows.append(
                    AuthorityGraphFinding(
                        "UNKNOWN_COMPONENT_EDGE",
                        tuple(sorted(missing)),
                        edge.contract_kind,
                        "edge references a component with no manifest",
                    )
                )
                continue

            implied = _RELATION_AUTHORITY.get(edge.relation)
            if implied is not None and implied in source.forbidden_authorities:
                rows.append(
                    AuthorityGraphFinding(
                        "FORBIDDEN_AUTHORITY_COMPOSITION",
                        (source.component_id, target.component_id),
                        implied,
                        f"{edge.relation.value} would grant a forbidden source authority",
                    )
                )

            if edge.relation in {AuthorityRelation.VERIFIES, AuthorityRelation.ASSURES} and source.component_id == target.component_id:
                rows.append(
                    AuthorityGraphFinding(
                        "SELF_VERIFICATION_LOOP",
                        (source.component_id,),
                        edge.contract_kind,
                        "verification/Assurance independence cannot self-loop",
                    )
                )

            if edge.contract_kind not in source.produces_contracts or edge.contract_kind not in target.consumes_contracts:
                rows.append(
                    AuthorityGraphFinding(
                        "UNDECLARED_CONTRACT_EDGE",
                        (source.component_id, target.component_id),
                        edge.contract_kind,
                        "producer/consumer manifests do not both declare this contract",
                    )
                )

        if self._has_escalating_cycle():
            rows.append(
                AuthorityGraphFinding(
                    "AUTHORITY_ESCALATION_CYCLE",
                    tuple(sorted(self._by_id)),
                    "authority-graph",
                    "authority-escalating edges contain a directed cycle",
                )
            )

        unique: dict[tuple[str, tuple[str, ...], str, str], AuthorityGraphFinding] = {}
        for row in rows:
            unique[(row.code, row.component_ids, row.subject, row.detail)] = row
        return tuple(
            sorted(
                unique.values(),
                key=lambda row: (row.code, row.component_ids, row.subject, row.detail),
            )
        )

    def validate(self) -> AuthorityGraphValidationReport:
        findings = self.findings()
        if findings:
            duplicate_writer = any(row.code == "DUPLICATE_CANONICAL_WRITER" for row in findings)
            if duplicate_writer:
                raise ValueError("duplicate canonical writer detected by authority graph")
            codes = ",".join(sorted({row.code for row in findings}))
            raise ValueError(f"authority graph validation failed: {codes}")
        payload = {"findings": []}
        return AuthorityGraphValidationReport((), canonical_digest(payload))

    def _duplicate_writer_findings(self) -> list[AuthorityGraphFinding]:
        owners: dict[str, list[str]] = {}
        for manifest in self._manifests:
            for resource in manifest.mutable_resources:
                owners.setdefault(resource, []).append(manifest.component_id)
        return [
            AuthorityGraphFinding(
                "DUPLICATE_CANONICAL_WRITER",
                tuple(sorted(component_ids)),
                resource,
                "multiple canonical components declare mutation authority for one resource",
            )
            for resource, component_ids in sorted(owners.items())
            if len(component_ids) > 1
        ]

    def _has_escalating_cycle(self) -> bool:
        adjacency: dict[str, set[str]] = {component_id: set() for component_id in self._by_id}
        for edge in self._edges:
            if edge.relation in _ESCALATING_RELATIONS and edge.source_component_id in adjacency and edge.target_component_id in adjacency:
                adjacency[edge.source_component_id].add(edge.target_component_id)

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for target in sorted(adjacency[node]):
                if visit(target):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in sorted(adjacency) if node not in visited)

    def _payload(self) -> dict[str, Any]:
        return {
            "manifests": [row.to_state() for row in self._manifests],
            "edges": [row.to_state() for row in self._edges],
        }

    def to_state(self) -> dict[str, Any]:
        payload = self._payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "ExternalAuthorityGraph":
        graph = cls(
            tuple(ExternalComponentManifest.from_state(raw) for raw in state.get("manifests", ())),
            tuple(AuthorityEdge.from_state(raw) for raw in state.get("edges", ())),
        )
        if str(state.get("digest", "")) != graph.digest:
            raise ValueError("authority graph digest mismatch")
        return graph


def _explicit(value: object, label: str) -> str:
    text = str(value)
    if not text.strip():
        raise ValueError(f"{label} must be explicit")
    return text


__all__ = (
    "AuthorityEdge",
    "AuthorityGraphFinding",
    "AuthorityGraphValidationReport",
    "AuthorityRelation",
    "ExternalAuthorityGraph",
)
