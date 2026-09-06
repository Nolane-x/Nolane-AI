from __future__ import annotations

import subprocess
from pathlib import Path


TARGET = Path("nolane/external_core/integration_admission_bundle.py")
EXPECTED_BLOB = "1e8e86f4a6007af64d98714f7b89698b8ec9e092"


def require_once(text: str, old: str, label: str) -> None:
    if text.count(old) != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {text.count(old)}")


def main() -> None:
    actual_blob = subprocess.check_output(
        ["git", "hash-object", str(TARGET)], text=True
    ).strip()
    if actual_blob != EXPECTED_BLOB:
        raise SystemExit(
            f"integration owner drifted before A10 apply: {actual_blob} != {EXPECTED_BLOB}"
        )

    text = TARGET.read_text()

    old = "from nolane.core.canonical_digest import canonical_digest, canonical_json\n"
    new = '''from nolane.core.canonical_digest import canonical_digest, canonical_json\nfrom nolane.external_core.observation import CanonicalObservationEnvelope, ObservationFinding\nfrom nolane.external_core.observation_integration import (\n    CANONICAL_OBSERVATION_CHAIN_ID,\n    build_observation_from_snapshot,\n    validate_observation_against_snapshot,\n)\n'''
    require_once(text, old, "observation imports")
    text = text.replace(old, new, 1)

    old = 'ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v3"\n'
    new = '''ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v3"\nCURRENT_ADMISSION_AUDIT_PROTOCOL = "external-integration-admission-audit-v4"\n'''
    require_once(text, old, "audit protocol")
    text = text.replace(old, new, 1)

    marker = "\n\n@dataclass(frozen=True, slots=True)\nclass AdmissionAuditFinding:"
    require_once(text, marker, "audit finding marker")
    builder = '''\n\ndef build_canonical_observation(\n    *,\n    observed_epoch: int = 0,\n    current_source_state_digests: Mapping[str, str] | None = None,\n    current_evidence_digests: Mapping[str, str] | None = None,\n    current_artifact_digests: Mapping[str, str] | None = None,\n    current_freshness_fences: Mapping[str, str] | None = None,\n    known_handoff_digests: Mapping[str, str] | None = None,\n    current_work_trace_digests: Mapping[str, str] | None = None,\n    chain_id: str = CANONICAL_OBSERVATION_CHAIN_ID,\n    previous_observation_digest: str | None = None,\n) -> CanonicalObservationEnvelope:\n    source = _frontier(current_source_state_digests)\n    evidence = _frontier(current_evidence_digests)\n    artifact = _frontier(current_artifact_digests)\n    freshness = _frontier(current_freshness_fences)\n    handoffs = _frontier(known_handoff_digests)\n    traces = _frontier(current_work_trace_digests)\n    registry, profile = _strict_current_objects()\n    return build_observation_from_snapshot(\n        registry,\n        profile,\n        observed_epoch=observed_epoch,\n        source=source,\n        evidence=evidence,\n        artifact=artifact,\n        freshness=freshness,\n        handoffs=handoffs,\n        traces=traces,\n        chain_id=chain_id,\n        previous_observation_digest=previous_observation_digest,\n    )\n'''
    text = text.replace(marker, builder + marker, 1)

    start = text.index(
        "@dataclass(frozen=True, slots=True)\nclass CanonicalAdmissionAuditReport:"
    )
    end = text.index("\n\ndef _append_readmission_findings(", start)
    report_block = '''@dataclass(frozen=True, slots=True)\nclass CanonicalAdmissionAuditReport:\n    protocol: str\n    findings: tuple[AdmissionAuditFinding, ...]\n    digest: str\n    observation_digest: str | None = None\n\n    @classmethod\n    def create(\n        cls,\n        findings: Sequence[AdmissionAuditFinding],\n        *,\n        current_observation: bool = False,\n        observation_digest: str | None = None,\n    ) -> "CanonicalAdmissionAuditReport":\n        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))\n        protocol = CURRENT_ADMISSION_AUDIT_PROTOCOL if current_observation else ADMISSION_AUDIT_PROTOCOL\n        payload: dict[str, Any] = {\n            "protocol": protocol,\n            "findings": [row.to_state() for row in rows],\n        }\n        namespace = "admission-audit-v4-" if current_observation else "admission-audit-v3-"\n        if current_observation:\n            payload["observation_digest"] = observation_digest\n        return cls(\n            protocol=protocol,\n            findings=rows,\n            digest=namespace + canonical_digest(payload),\n            observation_digest=observation_digest if current_observation else None,\n        )\n\n    def to_state(self) -> dict[str, Any]:\n        state: dict[str, Any] = {\n            "protocol": self.protocol,\n            "findings": [row.to_state() for row in self.findings],\n            "digest": self.digest,\n        }\n        if self.protocol == CURRENT_ADMISSION_AUDIT_PROTOCOL:\n            state["observation_digest"] = self.observation_digest\n        return state\n'''
    text = text[:start] + report_block + text[end:]

    run_start = text.index("def run_canonical_admission_audit(")
    run_end = text.index("\n\ndef _main(", run_start)
    run = text[run_start:run_end]

    old_sig = '''    current_work_trace_digests: Mapping[str, str] | None = None,\n) -> CanonicalAdmissionAuditReport:\n    persisted_bundle = bundle is not None\n'''
    new_sig = '''    current_work_trace_digests: Mapping[str, str] | None = None,\n    current_observation: CanonicalObservationEnvelope | None = None,\n    predecessor_observation: CanonicalObservationEnvelope | None = None,\n    competing_successors: Sequence[CanonicalObservationEnvelope] = (),\n    observation_genesis: bool | None = None,\n    observation_chain_id: str = CANONICAL_OBSERVATION_CHAIN_ID,\n) -> CanonicalAdmissionAuditReport:\n    current_observation_mode = (\n        observation_genesis is not None\n        or current_observation is not None\n        or predecessor_observation is not None\n        or bool(competing_successors)\n    )\n    current_observation_for_report = current_observation\n\n    def make_report(rows: Sequence[AdmissionAuditFinding]) -> CanonicalAdmissionAuditReport:\n        return CanonicalAdmissionAuditReport.create(\n            rows,\n            current_observation=current_observation_mode,\n            observation_digest=(\n                None\n                if current_observation_for_report is None\n                else current_observation_for_report.digest\n            ),\n        )\n\n    persisted_bundle = bundle is not None\n'''
    require_once(run, old_sig, "audit signature")
    run = run.replace(old_sig, new_sig, 1)
    run = run.replace("CanonicalAdmissionAuditReport.create(", "make_report(")
    run = run.replace(
        "return make_report(\n            rows,\n            current_observation=current_observation_mode,",
        "return CanonicalAdmissionAuditReport.create(\n            rows,\n            current_observation=current_observation_mode,",
        1,
    )

    needle = "    findings: list[AdmissionAuditFinding] = []\n"
    require_once(run, needle, "findings initialization")
    insert = '''    findings: list[AdmissionAuditFinding] = []\n\n    if current_observation_mode:\n        if type(observation_genesis) not in (bool, type(None)):\n            findings.append(\n                AdmissionAuditFinding(\n                    code="CURRENT_OBSERVATION_GENESIS_INVALID",\n                    detail="observation_genesis must be an exact boolean when supplied",\n                    subject_id="canonical-observation",\n                )\n            )\n        snapshot_values = (\n            current_source_state_digests,\n            current_evidence_digests,\n            current_artifact_digests,\n            current_freshness_fences,\n            known_handoff_digests,\n            current_work_trace_digests,\n        )\n        snapshot_available = not frontier_snapshot_errors and all(\n            row is not None for row in snapshot_values\n        )\n        if current_observation_for_report is None:\n            if observation_genesis is True and snapshot_available:\n                assert current_source_state_digests is not None\n                assert current_evidence_digests is not None\n                assert current_artifact_digests is not None\n                assert current_freshness_fences is not None\n                assert known_handoff_digests is not None\n                assert current_work_trace_digests is not None\n                current_observation_for_report = build_observation_from_snapshot(\n                    registry,\n                    profile,\n                    observed_epoch=bundle.context.observed_epoch,\n                    source=current_source_state_digests,\n                    evidence=current_evidence_digests,\n                    artifact=current_artifact_digests,\n                    freshness=current_freshness_fences,\n                    handoffs=known_handoff_digests,\n                    traces=current_work_trace_digests,\n                    chain_id=observation_chain_id,\n                    previous_observation_digest=None,\n                )\n            else:\n                findings.append(\n                    AdmissionAuditFinding(\n                        code="CURRENT_OBSERVATION_WITNESS_UNAVAILABLE",\n                        detail="current observation audit requires an explicit canonical observation witness",\n                        subject_id="canonical-observation",\n                    )\n                )\n\n        if current_observation_for_report is not None:\n            if not snapshot_available:\n                findings.append(\n                    AdmissionAuditFinding(\n                        code="CURRENT_OBSERVATION_SURFACE_UNAVAILABLE",\n                        detail="current observation witness cannot be re-attested without all six detached live frontiers",\n                        subject_id="canonical-observation",\n                    )\n                )\n            else:\n                assert current_source_state_digests is not None\n                assert current_evidence_digests is not None\n                assert current_artifact_digests is not None\n                assert current_freshness_fences is not None\n                assert known_handoff_digests is not None\n                assert current_work_trace_digests is not None\n                try:\n                    observation_findings = validate_observation_against_snapshot(\n                        current_observation_for_report,\n                        registry=registry,\n                        profile=profile,\n                        source=current_source_state_digests,\n                        evidence=current_evidence_digests,\n                        artifact=current_artifact_digests,\n                        freshness=current_freshness_fences,\n                        handoffs=known_handoff_digests,\n                        traces=current_work_trace_digests,\n                        predecessor=predecessor_observation,\n                        genesis=bool(observation_genesis),\n                        competing_successors=competing_successors,\n                    )\n                except (AttributeError, KeyError, TypeError, ValueError) as exc:\n                    findings.append(\n                        AdmissionAuditFinding(\n                            code="CURRENT_OBSERVATION_WITNESS_INVALID",\n                            detail=str(exc),\n                            subject_id="canonical-observation",\n                        )\n                    )\n                else:\n                    findings.extend(\n                        AdmissionAuditFinding(\n                            code=row.code,\n                            detail=row.detail,\n                            subject_id=row.subject_id,\n                        )\n                        for row in observation_findings\n                    )\n\n                observation_context_pairs = (\n                    ("registry", current_observation_for_report.registry_digest, bundle.context.registry_digest),\n                    ("authority-graph", current_observation_for_report.authority_graph_digest, bundle.context.authority_graph_digest),\n                    ("source-state", current_observation_for_report.source_state_frontier_digest, bundle.context.source_state_frontier_digest),\n                    ("evidence", current_observation_for_report.evidence_frontier_digest, bundle.context.evidence_frontier_digest),\n                    ("artifact", current_observation_for_report.artifact_frontier_digest, bundle.context.artifact_frontier_digest),\n                    ("freshness", current_observation_for_report.freshness_fence_frontier_digest, bundle.context.freshness_fence_frontier_digest),\n                    ("handoff", current_observation_for_report.handoff_frontier_digest, bundle.context.handoff_frontier_digest),\n                    ("work-trace", current_observation_for_report.work_trace_frontier_digest, bundle.context.work_trace_frontier_digest),\n                )\n                for kind, observation_digest, context_digest in observation_context_pairs:\n                    if observation_digest != context_digest:\n                        findings.append(\n                            AdmissionAuditFinding(\n                                code="OBSERVATION_ADMISSION_CONTEXT_MISMATCH",\n                                detail="canonical observation commitment does not match the audited admission context",\n                                subject_id=kind,\n                            )\n                        )\n                if current_observation_for_report.observed_epoch != bundle.context.observed_epoch:\n                    findings.append(\n                        AdmissionAuditFinding(\n                            code="OBSERVATION_ADMISSION_CONTEXT_MISMATCH",\n                            detail="canonical observation epoch does not match the audited admission context",\n                            subject_id="observed-epoch",\n                        )\n                    )\n'''
    run = run.replace(needle, insert, 1)
    text = text[:run_start] + run + text[run_end:]

    old_all = '''    "ADMISSION_AUDIT_PROTOCOL",\n    "ADMISSION_BUNDLE_PROTOCOL",\n'''
    new_all = '''    "ADMISSION_AUDIT_PROTOCOL",\n    "CURRENT_ADMISSION_AUDIT_PROTOCOL",\n    "ADMISSION_BUNDLE_PROTOCOL",\n'''
    require_once(text, old_all, "protocol exports")
    text = text.replace(old_all, new_all, 1)

    old_exports = '''    "build_canonical_admission_bundle",\n    "build_canonical_admission_context",\n'''
    new_exports = '''    "build_canonical_admission_bundle",\n    "build_canonical_admission_context",\n    "build_canonical_observation",\n'''
    require_once(text, old_exports, "builder exports")
    text = text.replace(old_exports, new_exports, 1)

    TARGET.write_text(text)
    subprocess.run(["python", "-m", "py_compile", str(TARGET)], check=True)


if __name__ == "__main__":
    main()
