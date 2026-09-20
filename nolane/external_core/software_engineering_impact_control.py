from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering import EngineeringPatchTransaction
from nolane.external_core.software_engineering_control import (
    EngineeringWorkRecord,
    SoftwareEngineeringControlPlane,
)
from nolane.external_core.software_engineering_impact import (
    EngineeringDependencyGraphLedger,
    EngineeringImpactAnalyzer,
    EngineeringImpactReceipt,
    EngineeringTestCoverageLedger,
    EngineeringTestSelectionEngine,
    EngineeringTestSelectionProof,
)
from nolane.external_core.software_engineering_policy import (
    EngineeringGateReceipt,
    EngineeringRiskClass,
)
from nolane.external_core.software_engineering_validity import (
    EngineeringCurrentValidityReceipt,
    EngineeringMutationAuthorityReceipt,
)


COMPONENT_ID = "external.software_engineering.impact_control"
COMPONENT_VERSION = "0.5.0"
CANONICAL_WRITE_AUTHORITY = False


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


@dataclass(frozen=True, slots=True)
class EngineeringImpactWorkBinding:
    binding_id: str
    work_id: str
    work_digest: str
    manifest_id: str
    manifest_digest: str
    graph_id: str
    graph_digest: str
    impact_id: str
    impact_digest: str
    coverage_id: str
    coverage_digest: str
    selection_id: str
    selection_digest: str
    authority: str
    digest: str

    def __post_init__(self) -> None:
        for value, field in (
            (self.binding_id, "impact binding id"),
            (self.work_id, "work id"),
            (self.work_digest, "work digest"),
            (self.manifest_id, "manifest id"),
            (self.manifest_digest, "manifest digest"),
            (self.graph_id, "graph id"),
            (self.graph_digest, "graph digest"),
            (self.impact_id, "impact id"),
            (self.impact_digest, "impact digest"),
            (self.coverage_id, "coverage id"),
            (self.coverage_digest, "coverage digest"),
            (self.selection_id, "selection id"),
            (self.selection_digest, "selection digest"),
            (self.digest, "impact binding digest"),
        ):
            _text(value, field=field)
        if self.authority != "evidence_only":
            raise ValueError("engineering impact binding authority must be evidence_only")

    def payload(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "work_digest": self.work_digest,
            "manifest_id": self.manifest_id,
            "manifest_digest": self.manifest_digest,
            "graph_id": self.graph_id,
            "graph_digest": self.graph_digest,
            "impact_id": self.impact_id,
            "impact_digest": self.impact_digest,
            "coverage_id": self.coverage_id,
            "coverage_digest": self.coverage_digest,
            "selection_id": self.selection_id,
            "selection_digest": self.selection_digest,
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"binding_id": self.binding_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringImpactWorkBinding":
        row = cls(
            binding_id=_text(state["binding_id"], field="impact binding id"),
            work_id=_text(state["work_id"], field="work id"),
            work_digest=_text(state["work_digest"], field="work digest"),
            manifest_id=_text(state["manifest_id"], field="manifest id"),
            manifest_digest=_text(state["manifest_digest"], field="manifest digest"),
            graph_id=_text(state["graph_id"], field="graph id"),
            graph_digest=_text(state["graph_digest"], field="graph digest"),
            impact_id=_text(state["impact_id"], field="impact id"),
            impact_digest=_text(state["impact_digest"], field="impact digest"),
            coverage_id=_text(state["coverage_id"], field="coverage id"),
            coverage_digest=_text(state["coverage_digest"], field="coverage digest"),
            selection_id=_text(state["selection_id"], field="selection id"),
            selection_digest=_text(state["selection_digest"], field="selection digest"),
            authority=_text(state["authority"], field="impact binding authority"),
            digest=_text(state["digest"], field="impact binding digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.binding_id != f"eng-impact-binding-{expected[:20]}":
            raise ValueError("engineering impact binding digest/id mismatch")
        return row


@dataclass(frozen=True, slots=True)
class EngineeringImpactCandidateReceipt:
    receipt_id: str
    work_id: str
    work_digest: str
    impact_binding_id: str
    impact_binding_digest: str
    inner_gate_receipt_id: str | None
    inner_gate_digest: str | None
    ready: bool
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        if self.authority != "candidate_only":
            raise ValueError("engineering impact candidate authority must be candidate_only")
        if bool(self.inner_gate_receipt_id) != bool(self.inner_gate_digest):
            raise ValueError("engineering impact candidate inner gate identity must be complete")
        if self.ready and (self.reasons or self.inner_gate_receipt_id is None):
            raise ValueError("ready impact candidate requires clean inner gate")
        if not self.ready and not self.reasons:
            raise ValueError("blocked impact candidate requires reasons")

    def payload(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "work_digest": self.work_digest,
            "impact_binding_id": self.impact_binding_id,
            "impact_binding_digest": self.impact_binding_digest,
            "inner_gate_receipt_id": self.inner_gate_receipt_id,
            "inner_gate_digest": self.inner_gate_digest,
            "ready": self.ready,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringImpactCandidateReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="impact candidate receipt id"),
            work_id=_text(state["work_id"], field="work id"),
            work_digest=_text(state["work_digest"], field="work digest"),
            impact_binding_id=_text(state["impact_binding_id"], field="impact binding id"),
            impact_binding_digest=_text(state["impact_binding_digest"], field="impact binding digest"),
            inner_gate_receipt_id=_optional_text(state.get("inner_gate_receipt_id")),
            inner_gate_digest=_optional_text(state.get("inner_gate_digest")),
            ready=bool(state["ready"]),
            reasons=_refs(tuple(state.get("reasons", ()))),
            authority=_text(state["authority"], field="impact candidate authority"),
            digest=_text(state["digest"], field="impact candidate digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-impact-gate-{expected[:20]}":
            raise ValueError("engineering impact candidate receipt digest/id mismatch")
        return row


class DerivedImpactEngineeringControl:
    """Strict F facade that derives blast radius and proves differential test coverage.

    The wrapped SoftwareEngineeringControlPlane remains the underlying governed F
    lifecycle. This facade adds an evidence-only impact layer and deliberately
    refuses to call inner candidate closure until the impact/test proof is closed.
    """

    def __init__(
        self,
        *,
        plane: SoftwareEngineeringControlPlane,
        dependency_graphs: EngineeringDependencyGraphLedger | None = None,
        test_coverage: EngineeringTestCoverageLedger | None = None,
        impacts: Mapping[str, EngineeringImpactReceipt] | None = None,
        selections: Mapping[str, EngineeringTestSelectionProof] | None = None,
        bindings: Mapping[str, EngineeringImpactWorkBinding] | None = None,
        receipts: Mapping[str, EngineeringImpactCandidateReceipt] | None = None,
    ) -> None:
        self.plane = plane
        self.dependency_graphs = dependency_graphs if dependency_graphs is not None else EngineeringDependencyGraphLedger()
        self.test_coverage = test_coverage if test_coverage is not None else EngineeringTestCoverageLedger()
        self._impacts = dict(impacts or {})
        self._selections = dict(selections or {})
        self._bindings = dict(bindings or {})
        self._binding_by_work = {row.work_id: row.binding_id for row in self._bindings.values()}
        if len(self._binding_by_work) != len(self._bindings):
            raise ValueError("engineering work has multiple impact bindings")
        self._receipts = dict(receipts or {})

    @property
    def digest(self) -> str:
        return canonical_digest(self._state_payload())

    def impact(self, impact_id: str) -> EngineeringImpactReceipt:
        try:
            return self._impacts[str(impact_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering impact receipt: {impact_id}") from exc

    def selection(self, selection_id: str) -> EngineeringTestSelectionProof:
        try:
            return self._selections[str(selection_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering test selection: {selection_id}") from exc

    def binding_for_work(self, work_id: str) -> EngineeringImpactWorkBinding:
        try:
            return self._bindings[self._binding_by_work[str(work_id)]]
        except KeyError as exc:
            raise KeyError(f"unknown engineering impact work binding: {work_id}") from exc

    def get(self, receipt_id: str) -> EngineeringImpactCandidateReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown engineering impact candidate receipt: {receipt_id}") from exc

    def begin_patch(
        self,
        *,
        patch: Any,
        source_revision: str,
        rollback_artifact_ref: str,
        claim_refs: tuple[str, ...],
        dependency_graph_id: str,
        test_coverage_id: str,
        claimed_impacted_component_refs: tuple[str, ...] | None = None,
        dependency_refs: tuple[str, ...] = (),
        declared_risk: EngineeringRiskClass = EngineeringRiskClass.LOW,
        ui_sensitive: bool = False,
        security_sensitive: bool = False,
        performance_sensitive: bool = False,
        debug_origin: bool = False,
    ) -> EngineeringWorkRecord:
        source = _text(source_revision, field="source revision")
        graph = self.dependency_graphs.get(dependency_graph_id)
        coverage = self.test_coverage.get(test_coverage_id)
        if graph.source_revision != source:
            raise ValueError("dependency graph source revision does not match engineering work")
        if coverage.source_revision != source:
            raise ValueError("test coverage source revision does not match engineering work")
        if coverage.graph_id != graph.graph_id or coverage.graph_digest != graph.digest:
            raise ValueError("test coverage dependency graph lineage mismatch")

        impact = EngineeringImpactAnalyzer().analyze(patch=patch, graph=graph)
        selection = EngineeringTestSelectionEngine().select(impact=impact, coverage=coverage)
        if claimed_impacted_component_refs is not None:
            declared = _refs(claimed_impacted_component_refs)
            if declared != impact.impacted_component_refs:
                raise ValueError("declared impact does not match derived impact")

        provenance_dependencies = _refs((
            *dependency_refs,
            *graph.provenance_refs,
            *coverage.provenance_refs,
            f"graph:{graph.graph_id}",
            f"coverage:{coverage.coverage_id}",
            f"impact:{impact.impact_id}",
            f"selection:{selection.selection_id}",
        ))
        work = self.plane.begin_patch(
            patch=patch,
            source_revision=source,
            rollback_artifact_ref=rollback_artifact_ref,
            claim_refs=claim_refs,
            dependency_refs=provenance_dependencies,
            impacted_component_refs=impact.impacted_component_refs,
            declared_risk=declared_risk,
            ui_sensitive=ui_sensitive,
            security_sensitive=security_sensitive,
            performance_sensitive=performance_sensitive,
            debug_origin=debug_origin,
        )
        manifest = self.plane.manifests.get(work.manifest_id)
        if manifest.impacted_component_refs != impact.impacted_component_refs:
            raise ValueError("engineering manifest does not preserve derived impact")

        payload = {
            "work_id": work.work_id,
            "work_digest": work.digest,
            "manifest_id": manifest.manifest_id,
            "manifest_digest": manifest.digest,
            "graph_id": graph.graph_id,
            "graph_digest": graph.digest,
            "impact_id": impact.impact_id,
            "impact_digest": impact.digest,
            "coverage_id": coverage.coverage_id,
            "coverage_digest": coverage.digest,
            "selection_id": selection.selection_id,
            "selection_digest": selection.digest,
            "authority": "evidence_only",
        }
        digest = canonical_digest(payload)
        binding = EngineeringImpactWorkBinding(
            binding_id=f"eng-impact-binding-{digest[:20]}",
            work_id=work.work_id,
            work_digest=work.digest,
            manifest_id=manifest.manifest_id,
            manifest_digest=manifest.digest,
            graph_id=graph.graph_id,
            graph_digest=graph.digest,
            impact_id=impact.impact_id,
            impact_digest=impact.digest,
            coverage_id=coverage.coverage_id,
            coverage_digest=coverage.digest,
            selection_id=selection.selection_id,
            selection_digest=selection.digest,
            authority="evidence_only",
            digest=digest,
        )
        old_binding_id = self._binding_by_work.get(work.work_id)
        if old_binding_id is not None and old_binding_id != binding.binding_id:
            raise ValueError("engineering work impact binding cannot be rebound")
        existing = self._bindings.get(binding.binding_id)
        if existing is not None and existing != binding:
            raise ValueError("engineering impact binding id cannot be rebound")
        self._impacts[impact.impact_id] = impact
        self._selections[selection.selection_id] = selection
        self._bindings[binding.binding_id] = binding
        self._binding_by_work[work.work_id] = binding.binding_id
        return work

    def record_evidence(self, **kwargs: Any) -> Any:
        return self.plane.record_evidence(**kwargs)

    def verify_preconditions(self, transaction_id: str, *, attestation_ids: tuple[str, ...]) -> EngineeringPatchTransaction:
        return self.plane.verify_preconditions(transaction_id, attestation_ids=attestation_ids)

    def assess_mutation_authority(self, work_id: str, *, patch: Any) -> EngineeringMutationAuthorityReceipt:
        return self.plane.assess_mutation_authority(work_id, patch=patch)

    def mark_applied(
        self,
        transaction_id: str,
        *,
        application_ref: str,
        mutation_authority_receipt_id: str | None = None,
    ) -> EngineeringPatchTransaction:
        return self.plane.mark_applied(
            transaction_id,
            application_ref=application_ref,
            mutation_authority_receipt_id=mutation_authority_receipt_id,
        )

    def observe_outcome(self, transaction_id: str, *, evidence_refs: tuple[str, ...]) -> EngineeringPatchTransaction:
        return self.plane.observe_outcome(transaction_id, evidence_refs=evidence_refs)

    def verify_postconditions(self, transaction_id: str, *, attestation_ids: tuple[str, ...]) -> EngineeringPatchTransaction:
        return self.plane.verify_postconditions(transaction_id, attestation_ids=attestation_ids)

    def _binding_reasons(
        self,
        *,
        work: EngineeringWorkRecord,
        binding: EngineeringImpactWorkBinding,
        patch: Any,
        current_source_revision: str,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        current_source = str(current_source_revision)
        manifest = self.plane.manifests.get(work.manifest_id)
        graph = self.dependency_graphs.get(binding.graph_id)
        coverage = self.test_coverage.get(binding.coverage_id)
        impact = self.impact(binding.impact_id)
        selection = self.selection(binding.selection_id)

        if binding.work_id != work.work_id or binding.work_digest != work.digest:
            reasons.append("impact_binding_work_lineage_mismatch")
        if binding.manifest_id != work.manifest_id or binding.manifest_digest != work.manifest_digest:
            reasons.append("impact_binding_manifest_lineage_mismatch")
        if graph.digest != binding.graph_digest:
            reasons.append("impact_binding_graph_lineage_mismatch")
        if coverage.digest != binding.coverage_digest:
            reasons.append("impact_binding_coverage_lineage_mismatch")
        if impact.digest != binding.impact_digest:
            reasons.append("impact_binding_impact_lineage_mismatch")
        if selection.digest != binding.selection_digest:
            reasons.append("impact_binding_selection_lineage_mismatch")
        if manifest.digest != binding.manifest_digest:
            reasons.append("manifest_impact_lineage_mismatch")
        if manifest.impacted_component_refs != impact.impacted_component_refs:
            reasons.append("manifest_impact_mismatch")
        if impact.graph_id != graph.graph_id or impact.graph_digest != graph.digest:
            reasons.append("impact_graph_lineage_mismatch")
        if impact.source_revision != current_source or graph.source_revision != current_source:
            reasons.append("impact_source_revision_mismatch")
        if coverage.source_revision != current_source:
            reasons.append("impact_coverage_source_revision_mismatch")
        if selection.impact_id != impact.impact_id or selection.impact_digest != impact.digest:
            reasons.append("selection_impact_lineage_mismatch")
        if selection.coverage_id != coverage.coverage_id or selection.coverage_digest != coverage.digest:
            reasons.append("selection_coverage_lineage_mismatch")
        if not hasattr(patch, "to_state"):
            reasons.append("missing_canonical_patch_state")
        else:
            if (
                str(getattr(patch, "patch_id", "")) != impact.patch_ref
                or canonical_digest(patch.to_state()) != impact.patch_digest
            ):
                reasons.append("impact_patch_lineage_mismatch")
        if not selection.complete or selection.uncovered_nodes:
            reasons.append("uncovered_impact_nodes")
        return tuple(sorted(set(reasons)))

    def assess_candidate(
        self,
        *,
        work_id: str,
        patch: Any,
        coding_readiness: Any,
        current_source_revision: str,
        attestation_ids: tuple[str, ...],
        debug_resolution: Any | None = None,
        ui_readiness: Any | None = None,
    ) -> EngineeringImpactCandidateReceipt:
        work = self.plane.work(work_id)
        binding = self.binding_for_work(work_id)
        reasons = list(self._binding_reasons(
            work=work,
            binding=binding,
            patch=patch,
            current_source_revision=current_source_revision,
        ))
        inner: EngineeringGateReceipt | None = None
        if not reasons:
            inner = self.plane.assess_candidate(
                work_id=work_id,
                patch=patch,
                coding_readiness=coding_readiness,
                current_source_revision=current_source_revision,
                attestation_ids=attestation_ids,
                debug_resolution=debug_resolution,
                ui_readiness=ui_readiness,
            )
            if not inner.ready:
                reasons.extend(inner.reasons)

        normalized = tuple(sorted(set(reasons)))
        ready = inner is not None and inner.ready and not normalized
        payload = {
            "work_id": work.work_id,
            "work_digest": work.digest,
            "impact_binding_id": binding.binding_id,
            "impact_binding_digest": binding.digest,
            "inner_gate_receipt_id": None if inner is None else inner.receipt_id,
            "inner_gate_digest": None if inner is None else inner.digest,
            "ready": ready,
            "reasons": list(normalized),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringImpactCandidateReceipt(
            receipt_id=f"eng-impact-gate-{digest[:20]}",
            work_id=work.work_id,
            work_digest=work.digest,
            impact_binding_id=binding.binding_id,
            impact_binding_digest=binding.digest,
            inner_gate_receipt_id=payload["inner_gate_receipt_id"],
            inner_gate_digest=payload["inner_gate_digest"],
            ready=ready,
            reasons=normalized,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("engineering impact candidate receipt cannot be rebound")
        self._receipts[row.receipt_id] = row
        return existing or row

    def revalidate(
        self,
        receipt_id: str,
        *,
        patch: Any,
        current_source_revision: str,
    ) -> EngineeringCurrentValidityReceipt:
        receipt = self.get(receipt_id)
        if not receipt.ready or receipt.inner_gate_receipt_id is None:
            raise PermissionError("blocked impact candidate has no closure to revalidate")
        work = self.plane.work(receipt.work_id)
        binding = self.binding_for_work(work.work_id)
        reasons = self._binding_reasons(
            work=work,
            binding=binding,
            patch=patch,
            current_source_revision=current_source_revision,
        )
        if reasons:
            raise PermissionError("impact proof is no longer current: " + ", ".join(reasons))
        return self.plane.revalidate(
            receipt.inner_gate_receipt_id,
            patch=patch,
            current_source_revision=current_source_revision,
        )

    def _state_payload(self) -> dict[str, Any]:
        return {
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "plane": self.plane.to_state(),
            "dependency_graphs": self.dependency_graphs.to_state(),
            "test_coverage": self.test_coverage.to_state(),
            "impacts": [self._impacts[key].to_state() for key in sorted(self._impacts)],
            "selections": [self._selections[key].to_state() for key in sorted(self._selections)],
            "bindings": [self._bindings[key].to_state() for key in sorted(self._bindings)],
            "receipts": [self._receipts[key].to_state() for key in sorted(self._receipts)],
        }

    def to_state(self) -> dict[str, Any]:
        payload = self._state_payload()
        return {**payload, "digest": canonical_digest(payload)}

    @classmethod
    def from_state(
        cls,
        *,
        claims: CodeClaimLedger,
        state: Mapping[str, Any],
    ) -> "DerivedImpactEngineeringControl":
        if _text(state["component_id"], field="component id") != COMPONENT_ID:
            raise ValueError("derived impact control component id mismatch")
        if _text(state["component_version"], field="component version") != COMPONENT_VERSION:
            raise ValueError("derived impact control component version mismatch")
        supplied_digest = _text(state["digest"], field="derived impact control digest")
        payload = {key: value for key, value in state.items() if key != "digest"}
        if canonical_digest(payload) != supplied_digest:
            raise ValueError("derived impact control snapshot digest mismatch")

        plane = SoftwareEngineeringControlPlane.from_state(claims=claims, state=state["plane"])
        graphs = EngineeringDependencyGraphLedger.from_state(state["dependency_graphs"])
        coverage = EngineeringTestCoverageLedger.from_state(state["test_coverage"])

        impacts: dict[str, EngineeringImpactReceipt] = {}
        for value in state.get("impacts", ()):
            row = EngineeringImpactReceipt.from_state(value)
            graph = graphs.get(row.graph_id)
            if row.graph_digest != graph.digest or row.source_revision != graph.source_revision:
                raise ValueError("impact snapshot graph lineage mismatch")
            old = impacts.get(row.impact_id)
            if old is not None and old != row:
                raise ValueError("duplicate/rebound impact receipt")
            impacts[row.impact_id] = row

        selections: dict[str, EngineeringTestSelectionProof] = {}
        for value in state.get("selections", ()):
            row = EngineeringTestSelectionProof.from_state(value)
            impact = impacts.get(row.impact_id)
            if impact is None or row.impact_digest != impact.digest:
                raise ValueError("selection snapshot impact lineage mismatch")
            coverage_row = coverage.get(row.coverage_id)
            if row.coverage_digest != coverage_row.digest:
                raise ValueError("selection snapshot coverage lineage mismatch")
            old = selections.get(row.selection_id)
            if old is not None and old != row:
                raise ValueError("duplicate/rebound test selection")
            selections[row.selection_id] = row

        bindings: dict[str, EngineeringImpactWorkBinding] = {}
        work_to_binding: dict[str, str] = {}
        for value in state.get("bindings", ()):
            row = EngineeringImpactWorkBinding.from_state(value)
            work = plane.work(row.work_id)
            manifest = plane.manifests.get(row.manifest_id)
            graph = graphs.get(row.graph_id)
            impact = impacts.get(row.impact_id)
            coverage_row = coverage.get(row.coverage_id)
            selection = selections.get(row.selection_id)
            if work.digest != row.work_digest:
                raise ValueError("impact binding work lineage mismatch")
            if manifest.digest != row.manifest_digest or work.manifest_id != manifest.manifest_id:
                raise ValueError("impact binding manifest lineage mismatch")
            if graph.digest != row.graph_digest:
                raise ValueError("impact binding graph lineage mismatch")
            if impact is None or impact.digest != row.impact_digest:
                raise ValueError("impact binding impact lineage mismatch")
            if coverage_row.digest != row.coverage_digest:
                raise ValueError("impact binding coverage lineage mismatch")
            if selection is None or selection.digest != row.selection_digest:
                raise ValueError("impact binding selection lineage mismatch")
            if selection.impact_id != impact.impact_id or selection.coverage_id != coverage_row.coverage_id:
                raise ValueError("impact binding selection cross-lineage mismatch")
            if manifest.impacted_component_refs != impact.impacted_component_refs:
                raise ValueError("impact binding manifest impact mismatch")
            prior = work_to_binding.get(row.work_id)
            if prior is not None and prior != row.binding_id:
                raise ValueError("engineering work has multiple impact bindings")
            bindings[row.binding_id] = row
            work_to_binding[row.work_id] = row.binding_id

        receipts: dict[str, EngineeringImpactCandidateReceipt] = {}
        for value in state.get("receipts", ()):
            row = EngineeringImpactCandidateReceipt.from_state(value)
            work = plane.work(row.work_id)
            binding = bindings.get(row.impact_binding_id)
            if work.digest != row.work_digest:
                raise ValueError("impact candidate work lineage mismatch")
            if binding is None or binding.digest != row.impact_binding_digest:
                raise ValueError("impact candidate binding lineage mismatch")
            if binding.work_id != work.work_id:
                raise ValueError("impact candidate binding work mismatch")
            if row.inner_gate_receipt_id is not None:
                inner = plane.gate.get(row.inner_gate_receipt_id)
                if inner.digest != row.inner_gate_digest:
                    raise ValueError("impact candidate inner gate lineage mismatch")
                if row.ready and not inner.ready:
                    raise ValueError("ready impact candidate references blocked inner gate")
            elif row.ready:
                raise ValueError("ready impact candidate missing inner gate")
            old = receipts.get(row.receipt_id)
            if old is not None and old != row:
                raise ValueError("duplicate/rebound impact candidate receipt")
            receipts[row.receipt_id] = row

        control = cls(
            plane=plane,
            dependency_graphs=graphs,
            test_coverage=coverage,
            impacts=impacts,
            selections=selections,
            bindings=bindings,
            receipts=receipts,
        )
        if control.digest != supplied_digest:
            raise ValueError("derived impact control restore is not state-identical")
        return control


__all__ = (
    "EngineeringImpactWorkBinding",
    "EngineeringImpactCandidateReceipt",
    "DerivedImpactEngineeringControl",
)
