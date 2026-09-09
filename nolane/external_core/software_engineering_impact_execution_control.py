from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from nolane.core.canonical_digest import canonical_digest
from nolane.external_core.coding_claims import CodeClaimLedger
from nolane.external_core.software_engineering import (
    EngineeringEvidenceKind,
    EngineeringPatchTransaction,
)
from nolane.external_core.software_engineering_control import (
    EngineeringWorkRecord,
    SoftwareEngineeringControlPlane,
)
from nolane.external_core.software_engineering_impact import (
    EngineeringDependencyGraphLedger,
    EngineeringImpactReceipt,
    EngineeringTestCoverageLedger,
    EngineeringTestSelectionProof,
)
from nolane.external_core.software_engineering_impact_control import (
    DerivedImpactEngineeringControl,
    EngineeringImpactCandidateReceipt,
    EngineeringImpactWorkBinding,
)
from nolane.external_core.software_engineering_impact_execution import (
    EngineeringTestExecutionLedger,
    EngineeringTestExecutionReceipt,
)
from nolane.external_core.software_engineering_policy import EngineeringRiskClass
from nolane.external_core.software_engineering_validity import (
    EngineeringCurrentValidityReceipt,
    EngineeringMutationAuthorityReceipt,
)


COMPONENT_ID = "external.software_engineering.impact_execution_control"
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
class EngineeringExecutionBoundCandidateReceipt:
    receipt_id: str
    work_id: str
    work_digest: str
    impact_binding_id: str
    impact_binding_digest: str
    test_execution_id: str | None
    test_execution_digest: str | None
    test_attestation_id: str | None
    test_attestation_digest: str | None
    impact_candidate_receipt_id: str | None
    impact_candidate_digest: str | None
    inner_gate_receipt_id: str | None
    inner_gate_digest: str | None
    ready: bool
    reasons: tuple[str, ...]
    authority: str
    digest: str

    def __post_init__(self) -> None:
        if self.authority != "candidate_only":
            raise ValueError("execution-bound impact candidate authority must be candidate_only")
        for left, right, label in (
            (self.test_execution_id, self.test_execution_digest, "test execution"),
            (self.test_attestation_id, self.test_attestation_digest, "test attestation"),
            (self.impact_candidate_receipt_id, self.impact_candidate_digest, "impact candidate"),
            (self.inner_gate_receipt_id, self.inner_gate_digest, "inner gate"),
        ):
            if bool(left) != bool(right):
                raise ValueError(f"execution-bound candidate {label} identity must be complete")
        if self.ready:
            if self.reasons:
                raise ValueError("ready execution-bound candidate cannot contain reasons")
            if not all((
                self.test_execution_id,
                self.test_attestation_id,
                self.impact_candidate_receipt_id,
                self.inner_gate_receipt_id,
            )):
                raise ValueError("ready execution-bound candidate requires complete proof lineage")
        elif not self.reasons:
            raise ValueError("blocked execution-bound candidate requires reasons")

    def payload(self) -> dict[str, Any]:
        return {
            "work_id": self.work_id,
            "work_digest": self.work_digest,
            "impact_binding_id": self.impact_binding_id,
            "impact_binding_digest": self.impact_binding_digest,
            "test_execution_id": self.test_execution_id,
            "test_execution_digest": self.test_execution_digest,
            "test_attestation_id": self.test_attestation_id,
            "test_attestation_digest": self.test_attestation_digest,
            "impact_candidate_receipt_id": self.impact_candidate_receipt_id,
            "impact_candidate_digest": self.impact_candidate_digest,
            "inner_gate_receipt_id": self.inner_gate_receipt_id,
            "inner_gate_digest": self.inner_gate_digest,
            "ready": self.ready,
            "reasons": list(self.reasons),
            "authority": self.authority,
        }

    def to_state(self) -> dict[str, Any]:
        return {"receipt_id": self.receipt_id, **self.payload(), "digest": self.digest}

    @classmethod
    def from_state(cls, state: Mapping[str, Any]) -> "EngineeringExecutionBoundCandidateReceipt":
        row = cls(
            receipt_id=_text(state["receipt_id"], field="execution-bound candidate receipt id"),
            work_id=_text(state["work_id"], field="work id"),
            work_digest=_text(state["work_digest"], field="work digest"),
            impact_binding_id=_text(state["impact_binding_id"], field="impact binding id"),
            impact_binding_digest=_text(state["impact_binding_digest"], field="impact binding digest"),
            test_execution_id=_optional_text(state.get("test_execution_id")),
            test_execution_digest=_optional_text(state.get("test_execution_digest")),
            test_attestation_id=_optional_text(state.get("test_attestation_id")),
            test_attestation_digest=_optional_text(state.get("test_attestation_digest")),
            impact_candidate_receipt_id=_optional_text(state.get("impact_candidate_receipt_id")),
            impact_candidate_digest=_optional_text(state.get("impact_candidate_digest")),
            inner_gate_receipt_id=_optional_text(state.get("inner_gate_receipt_id")),
            inner_gate_digest=_optional_text(state.get("inner_gate_digest")),
            ready=bool(state["ready"]),
            reasons=_refs(tuple(state.get("reasons", ()))),
            authority=_text(state["authority"], field="execution-bound candidate authority"),
            digest=_text(state["digest"], field="execution-bound candidate digest"),
        )
        expected = canonical_digest(row.payload())
        if row.digest != expected or row.receipt_id != f"eng-impact-exec-gate-{expected[:20]}":
            raise ValueError("execution-bound engineering candidate digest/id mismatch")
        return row


class ExecutionBoundDerivedImpactEngineeringControl:
    """Strongest v0.5 F facade: impact -> selection -> execution -> TEST evidence.

    This layer never calls the derived-impact candidate gate until the exact
    selected tests have an execution receipt and that receipt is named as a
    dependency of a live independent TEST attestation for the exact patch.
    """

    def __init__(
        self,
        *,
        plane: SoftwareEngineeringControlPlane | None = None,
        dependency_graphs: EngineeringDependencyGraphLedger | None = None,
        test_coverage: EngineeringTestCoverageLedger | None = None,
        impact_control: DerivedImpactEngineeringControl | None = None,
        test_executions: EngineeringTestExecutionLedger | None = None,
        execution_by_work: Mapping[str, str] | None = None,
        receipts: Mapping[str, EngineeringExecutionBoundCandidateReceipt] | None = None,
    ) -> None:
        if impact_control is None:
            if plane is None:
                raise ValueError("execution-bound impact control requires an engineering control plane")
            impact_control = DerivedImpactEngineeringControl(
                plane=plane,
                dependency_graphs=dependency_graphs,
                test_coverage=test_coverage,
            )
        self.impact_control = impact_control
        self.test_executions = test_executions if test_executions is not None else EngineeringTestExecutionLedger()
        self._execution_by_work = dict(execution_by_work or {})
        self._receipts = dict(receipts or {})

    @property
    def plane(self) -> SoftwareEngineeringControlPlane:
        return self.impact_control.plane

    @property
    def dependency_graphs(self) -> EngineeringDependencyGraphLedger:
        return self.impact_control.dependency_graphs

    @property
    def test_coverage(self) -> EngineeringTestCoverageLedger:
        return self.impact_control.test_coverage

    @property
    def digest(self) -> str:
        return canonical_digest(self._state_payload())

    def binding_for_work(self, work_id: str) -> EngineeringImpactWorkBinding:
        return self.impact_control.binding_for_work(work_id)

    def impact(self, impact_id: str) -> EngineeringImpactReceipt:
        return self.impact_control.impact(impact_id)

    def selection(self, selection_id: str) -> EngineeringTestSelectionProof:
        return self.impact_control.selection(selection_id)

    def get(self, receipt_id: str) -> EngineeringExecutionBoundCandidateReceipt:
        try:
            return self._receipts[str(receipt_id)]
        except KeyError as exc:
            raise KeyError(f"unknown execution-bound engineering candidate receipt: {receipt_id}") from exc

    def test_execution_for_work(self, work_id: str) -> EngineeringTestExecutionReceipt:
        try:
            execution_id = self._execution_by_work[str(work_id)]
        except KeyError as exc:
            raise KeyError(f"engineering work has no differential test execution: {work_id}") from exc
        return self.test_executions.get(execution_id)

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
        return self.impact_control.begin_patch(
            patch=patch,
            source_revision=source_revision,
            rollback_artifact_ref=rollback_artifact_ref,
            claim_refs=claim_refs,
            dependency_graph_id=dependency_graph_id,
            test_coverage_id=test_coverage_id,
            claimed_impacted_component_refs=claimed_impacted_component_refs,
            dependency_refs=dependency_refs,
            declared_risk=declared_risk,
            ui_sensitive=ui_sensitive,
            security_sensitive=security_sensitive,
            performance_sensitive=performance_sensitive,
            debug_origin=debug_origin,
        )

    def record_test_execution(
        self,
        work_id: str,
        *,
        source_revision: str,
        environment_digest: str,
        executed_tests: tuple[str, ...],
        failed_tests: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> EngineeringTestExecutionReceipt:
        work = self.plane.work(work_id)
        binding = self.binding_for_work(work_id)
        selection = self.selection(binding.selection_id)
        if source_revision != work.source_revision:
            raise ValueError("test execution source revision does not match engineering work")
        receipt = self.test_executions.record(
            selection=selection,
            source_revision=source_revision,
            environment_digest=environment_digest,
            executed_tests=executed_tests,
            failed_tests=failed_tests,
            evidence_refs=evidence_refs,
        )
        prior = self._execution_by_work.get(work.work_id)
        if prior is not None and prior != receipt.execution_id:
            raise ValueError("engineering work differential test execution cannot be rebound")
        self._execution_by_work[work.work_id] = receipt.execution_id
        return receipt

    def record_evidence(self, **kwargs: Any) -> Any:
        return self.impact_control.record_evidence(**kwargs)

    def verify_preconditions(self, transaction_id: str, *, attestation_ids: tuple[str, ...]) -> EngineeringPatchTransaction:
        return self.impact_control.verify_preconditions(transaction_id, attestation_ids=attestation_ids)

    def assess_mutation_authority(self, work_id: str, *, patch: Any) -> EngineeringMutationAuthorityReceipt:
        return self.impact_control.assess_mutation_authority(work_id, patch=patch)

    def mark_applied(
        self,
        transaction_id: str,
        *,
        application_ref: str,
        mutation_authority_receipt_id: str | None = None,
    ) -> EngineeringPatchTransaction:
        return self.impact_control.mark_applied(
            transaction_id,
            application_ref=application_ref,
            mutation_authority_receipt_id=mutation_authority_receipt_id,
        )

    def observe_outcome(self, transaction_id: str, *, evidence_refs: tuple[str, ...]) -> EngineeringPatchTransaction:
        return self.impact_control.observe_outcome(transaction_id, evidence_refs=evidence_refs)

    def verify_postconditions(self, transaction_id: str, *, attestation_ids: tuple[str, ...]) -> EngineeringPatchTransaction:
        return self.impact_control.verify_postconditions(transaction_id, attestation_ids=attestation_ids)

    def _execution_proof(
        self,
        *,
        work: EngineeringWorkRecord,
        attestation_ids: tuple[str, ...],
    ) -> tuple[EngineeringTestExecutionReceipt | None, str | None, tuple[str, ...]]:
        reasons: list[str] = []
        try:
            execution = self.test_execution_for_work(work.work_id)
        except KeyError:
            return None, None, ("missing_differential_test_execution",)

        binding = self.binding_for_work(work.work_id)
        selection = self.selection(binding.selection_id)
        if execution.selection_id != selection.selection_id or execution.selection_digest != selection.digest:
            reasons.append("differential_test_execution_selection_mismatch")
        if execution.source_revision != work.source_revision:
            reasons.append("differential_test_execution_source_mismatch")
        if not execution.passed:
            reasons.append("differential_test_execution_failed")

        dependency_ref = f"execution:{execution.execution_id}"
        test_attestation_id: str | None = None
        for attestation_id in sorted(set(attestation_ids)):
            try:
                row = self.plane.evidence.get(attestation_id)
            except KeyError:
                continue
            if row.kind is not EngineeringEvidenceKind.TEST:
                continue
            if dependency_ref not in row.dependencies:
                continue
            if not self.plane.evidence.is_valid(
                row.attestation_id,
                subject_ref=work.patch_ref,
                subject_digest=work.patch_digest,
                source_revision=work.source_revision,
            ):
                continue
            test_attestation_id = row.attestation_id
            break
        if test_attestation_id is None:
            reasons.append("test_attestation_not_bound_to_execution")
        return execution, test_attestation_id, tuple(sorted(set(reasons)))

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
    ) -> EngineeringExecutionBoundCandidateReceipt:
        work = self.plane.work(work_id)
        binding = self.binding_for_work(work_id)
        execution, test_attestation_id, execution_reasons = self._execution_proof(
            work=work,
            attestation_ids=attestation_ids,
        )
        reasons = list(execution_reasons)
        impact_candidate: EngineeringImpactCandidateReceipt | None = None
        if not reasons:
            impact_candidate = self.impact_control.assess_candidate(
                work_id=work_id,
                patch=patch,
                coding_readiness=coding_readiness,
                current_source_revision=current_source_revision,
                attestation_ids=attestation_ids,
                debug_resolution=debug_resolution,
                ui_readiness=ui_readiness,
            )
            if not impact_candidate.ready:
                reasons.extend(impact_candidate.reasons)

        test_attestation = None if test_attestation_id is None else self.plane.evidence.get(test_attestation_id)
        normalized = tuple(sorted(set(reasons)))
        ready = impact_candidate is not None and impact_candidate.ready and not normalized
        payload = {
            "work_id": work.work_id,
            "work_digest": work.digest,
            "impact_binding_id": binding.binding_id,
            "impact_binding_digest": binding.digest,
            "test_execution_id": None if execution is None else execution.execution_id,
            "test_execution_digest": None if execution is None else execution.digest,
            "test_attestation_id": test_attestation_id,
            "test_attestation_digest": None if test_attestation is None else test_attestation.digest,
            "impact_candidate_receipt_id": None if impact_candidate is None else impact_candidate.receipt_id,
            "impact_candidate_digest": None if impact_candidate is None else impact_candidate.digest,
            "inner_gate_receipt_id": None if impact_candidate is None else impact_candidate.inner_gate_receipt_id,
            "inner_gate_digest": None if impact_candidate is None else impact_candidate.inner_gate_digest,
            "ready": ready,
            "reasons": list(normalized),
            "authority": "candidate_only",
        }
        digest = canonical_digest(payload)
        row = EngineeringExecutionBoundCandidateReceipt(
            receipt_id=f"eng-impact-exec-gate-{digest[:20]}",
            work_id=work.work_id,
            work_digest=work.digest,
            impact_binding_id=binding.binding_id,
            impact_binding_digest=binding.digest,
            test_execution_id=payload["test_execution_id"],
            test_execution_digest=payload["test_execution_digest"],
            test_attestation_id=test_attestation_id,
            test_attestation_digest=payload["test_attestation_digest"],
            impact_candidate_receipt_id=payload["impact_candidate_receipt_id"],
            impact_candidate_digest=payload["impact_candidate_digest"],
            inner_gate_receipt_id=payload["inner_gate_receipt_id"],
            inner_gate_digest=payload["inner_gate_digest"],
            ready=ready,
            reasons=normalized,
            authority="candidate_only",
            digest=digest,
        )
        existing = self._receipts.get(row.receipt_id)
        if existing is not None and existing != row:
            raise ValueError("execution-bound engineering candidate receipt cannot be rebound")
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
        if not receipt.ready or receipt.impact_candidate_receipt_id is None:
            raise PermissionError("blocked execution-bound candidate has no closure to revalidate")
        work = self.plane.work(receipt.work_id)
        execution, attestation_id, reasons = self._execution_proof(
            work=work,
            attestation_ids=() if receipt.test_attestation_id is None else (receipt.test_attestation_id,),
        )
        if reasons:
            raise PermissionError("differential test execution proof is no longer current: " + ", ".join(reasons))
        if execution is None or execution.execution_id != receipt.test_execution_id or execution.digest != receipt.test_execution_digest:
            raise PermissionError("differential test execution lineage changed")
        if attestation_id != receipt.test_attestation_id:
            raise PermissionError("differential test attestation lineage changed")
        return self.impact_control.revalidate(
            receipt.impact_candidate_receipt_id,
            patch=patch,
            current_source_revision=current_source_revision,
        )

    def _state_payload(self) -> dict[str, Any]:
        return {
            "component_id": COMPONENT_ID,
            "component_version": COMPONENT_VERSION,
            "impact_control": self.impact_control.to_state(),
            "test_executions": self.test_executions.to_state(),
            "execution_by_work": [
                {"work_id": work_id, "execution_id": self._execution_by_work[work_id]}
                for work_id in sorted(self._execution_by_work)
            ],
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
    ) -> "ExecutionBoundDerivedImpactEngineeringControl":
        if _text(state["component_id"], field="component id") != COMPONENT_ID:
            raise ValueError("execution-bound impact control component id mismatch")
        if _text(state["component_version"], field="component version") != COMPONENT_VERSION:
            raise ValueError("execution-bound impact control component version mismatch")
        supplied_digest = _text(state["digest"], field="execution-bound impact control digest")
        payload = {key: value for key, value in state.items() if key != "digest"}
        if canonical_digest(payload) != supplied_digest:
            raise ValueError("execution-bound impact control snapshot digest mismatch")

        impact_control = DerivedImpactEngineeringControl.from_state(
            claims=claims,
            state=state["impact_control"],
        )
        executions = EngineeringTestExecutionLedger.from_state(state["test_executions"])
        execution_by_work: dict[str, str] = {}
        for value in state.get("execution_by_work", ()):
            work_id = _text(value["work_id"], field="execution work id")
            execution_id = _text(value["execution_id"], field="test execution id")
            if work_id in execution_by_work and execution_by_work[work_id] != execution_id:
                raise ValueError("engineering work has multiple differential test executions")
            work = impact_control.plane.work(work_id)
            binding = impact_control.binding_for_work(work_id)
            selection = impact_control.selection(binding.selection_id)
            execution = executions.get(execution_id)
            if execution.selection_id != selection.selection_id or execution.selection_digest != selection.digest:
                raise ValueError("test execution selection lineage mismatch")
            if execution.source_revision != work.source_revision:
                raise ValueError("test execution source lineage mismatch")
            if tuple(sorted(execution.required_tests)) != tuple(sorted(selection.selected_tests)):
                raise ValueError("test execution required tests do not match selection")
            execution_by_work[work_id] = execution_id

        receipts: dict[str, EngineeringExecutionBoundCandidateReceipt] = {}
        for value in state.get("receipts", ()):
            row = EngineeringExecutionBoundCandidateReceipt.from_state(value)
            work = impact_control.plane.work(row.work_id)
            binding = impact_control.binding_for_work(row.work_id)
            if work.digest != row.work_digest:
                raise ValueError("execution-bound candidate work lineage mismatch")
            if binding.binding_id != row.impact_binding_id or binding.digest != row.impact_binding_digest:
                raise ValueError("execution-bound candidate impact binding lineage mismatch")
            if row.test_execution_id is not None:
                execution = executions.get(row.test_execution_id)
                if execution.digest != row.test_execution_digest:
                    raise ValueError("execution-bound candidate test execution lineage mismatch")
                if execution_by_work.get(row.work_id) != execution.execution_id:
                    raise ValueError("execution-bound candidate work execution linkage mismatch")
            if row.test_attestation_id is not None:
                attestation = impact_control.plane.evidence.get(row.test_attestation_id)
                if attestation.digest != row.test_attestation_digest:
                    raise ValueError("execution-bound candidate test attestation lineage mismatch")
                if row.test_execution_id is None or f"execution:{row.test_execution_id}" not in attestation.dependencies:
                    raise ValueError("execution-bound candidate attestation execution lineage mismatch")
            if row.impact_candidate_receipt_id is not None:
                impact_candidate = impact_control.get(row.impact_candidate_receipt_id)
                if impact_candidate.digest != row.impact_candidate_digest:
                    raise ValueError("execution-bound candidate impact receipt lineage mismatch")
                if impact_candidate.inner_gate_receipt_id != row.inner_gate_receipt_id or impact_candidate.inner_gate_digest != row.inner_gate_digest:
                    raise ValueError("execution-bound candidate inner gate lineage mismatch")
                if row.ready and not impact_candidate.ready:
                    raise ValueError("ready execution-bound candidate references blocked impact candidate")
            elif row.ready:
                raise ValueError("ready execution-bound candidate missing impact candidate receipt")
            old = receipts.get(row.receipt_id)
            if old is not None and old != row:
                raise ValueError("duplicate/rebound execution-bound candidate receipt")
            receipts[row.receipt_id] = row

        control = cls(
            impact_control=impact_control,
            test_executions=executions,
            execution_by_work=execution_by_work,
            receipts=receipts,
        )
        if control.digest != supplied_digest:
            raise ValueError("execution-bound impact control restore is not state-identical")
        return control


__all__ = (
    "EngineeringExecutionBoundCandidateReceipt",
    "ExecutionBoundDerivedImpactEngineeringControl",
)
