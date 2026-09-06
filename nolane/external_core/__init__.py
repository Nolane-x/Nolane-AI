"""Canonical extra-neural cognition and engineering substrate namespace.

The conceptual External Core is intentionally wider than the invokable
ExternalCoreRegistry: it also contains persistent memory, context, planning,
architecture, evidence-backed engineering and other governed cognition.

The A2/A3, integration-evolution, scoped-revalidation and A5 admission exports
below are deliberately structural and authority-neutral. They expose immutable
contracts, registry provenance, validation, discovery, restore classification,
compatibility/impact structure, exact-context evidence binding, strict current
admission and read-only audit surfaces; they do not expose an invocation,
authorization, promotion, deployment, repair, Assurance, Verification, runtime
registration or migration path.
"""

from nolane.external_core.authority_graph import (
    AuthorityEdge,
    AuthorityGraphFinding,
    AuthorityGraphValidationReport,
    AuthorityRelation,
    ExternalAuthorityGraph,
)
from nolane.external_core.capability_discovery import (
    CapabilityDescriptor,
    CapabilityDiscoveryIndex,
    ContractDiscoveryResult,
    RegistryCapabilityDiscoveryIndex,
)
from nolane.external_core.coherence_audit import (
    CoherenceAuditReport,
    CoherenceFinding,
    ExternalCoreRestoreSnapshot,
    RestorePreflightResult,
    artifact_state_digest,
    audit_external_core,
    audit_live_external_core,
    preflight_restore,
)
from nolane.external_core.component_contracts import (
    ExternalComponentManifest,
    ExternalCoreFamily,
)
from nolane.external_core.evidence import ScopedEvidenceRecord
from nolane.external_core.handoff import (
    ExternalHandoffEnvelope,
    HandoffAuthorityClass,
    HandoffValidationDisposition,
    HandoffValidationResult,
    validate_handoff_for_consumer,
)
from nolane.external_core.integration_admission import (
    AdmissionDisposition,
    AdmissionSubjectKind,
    AdmittedAuthorityGraph,
    AdmittedHandoff,
    AdmittedManifest,
    AdmittedWorkTrace,
    CanonicalAdmissionContext,
    ProtocolAdmissionReceipt,
    admit_authority_graph_state,
    admit_handoff_state,
    admit_manifest_state,
    admit_work_trace_state,
    canonical_frontier_digest,
)
from nolane.external_core.integration_admission_bundle import (
    AdmissionAuditFinding,
    CanonicalAdmissionAuditReport,
    CanonicalAdmissionBundle,
    build_canonical_admission_bundle,
    build_canonical_admission_context,
    run_canonical_admission_audit,
)
from nolane.external_core.integration_evolution import (
    ComponentEvolutionDelta,
    EvolutionCompatibilityDisposition,
    EvolutionCompatibilityQualification,
    IntegrationImpactClosure,
    IntegrationImpactReason,
    build_integration_impact_closure,
    qualify_component_evolution,
)
from nolane.external_core.integration_revalidation import (
    ComponentRevalidationRequirement,
    RevalidationAssessment,
    RevalidationDisposition,
    RevalidationEvidenceBinding,
    RevalidationPlan,
    assess_revalidation,
    build_revalidation_plan,
)
from nolane.external_core.integration_scoped_revalidation import (
    RevalidationChallenge,
    RevalidationCompletionReceipt,
    RevalidationScope,
    ScopedRevalidationAssessment,
    ScopedRevalidationEvidenceBinding,
    assess_scoped_revalidation,
    build_revalidation_challenges,
    build_revalidation_scope,
    challenge_subject_digest,
)
from nolane.external_core.live_fabric import (
    LiveExternalCoreSnapshot,
    LiveRestoreAssessment,
    LiveRestoreDisposition,
    assess_live_restore,
    assess_live_restore_state,
    handoff_frontier_digest,
    source_state_frontier_digest,
    work_trace_frontier_digest,
)
from nolane.external_core.registry import (
    CapabilityCatalogBindingReceipt,
    CanonicalComponentRegistry,
    ManifestAdapter,
    RegistryCoverageFinding,
    RegistryCoverageReport,
)
from nolane.external_core.work_trace import (
    CognitiveWorkTrace,
    TraceDiagnostic,
    TraceNode,
    TraceNodeStatus,
    TraceSupersessionReceipt,
)


__all__ = (
    "AdmissionAuditFinding",
    "AdmissionDisposition",
    "AdmissionSubjectKind",
    "AdmittedAuthorityGraph",
    "AdmittedHandoff",
    "AdmittedManifest",
    "AdmittedWorkTrace",
    "AuthorityEdge",
    "AuthorityGraphFinding",
    "AuthorityGraphValidationReport",
    "AuthorityRelation",
    "CapabilityCatalogBindingReceipt",
    "CapabilityDescriptor",
    "CapabilityDiscoveryIndex",
    "CanonicalAdmissionAuditReport",
    "CanonicalAdmissionBundle",
    "CanonicalAdmissionContext",
    "CanonicalComponentRegistry",
    "CognitiveWorkTrace",
    "CoherenceAuditReport",
    "CoherenceFinding",
    "ComponentEvolutionDelta",
    "ComponentRevalidationRequirement",
    "ContractDiscoveryResult",
    "EvolutionCompatibilityDisposition",
    "EvolutionCompatibilityQualification",
    "ExternalAuthorityGraph",
    "ExternalComponentManifest",
    "ExternalCoreFamily",
    "ExternalCoreRestoreSnapshot",
    "ExternalHandoffEnvelope",
    "HandoffAuthorityClass",
    "HandoffValidationDisposition",
    "HandoffValidationResult",
    "IntegrationImpactClosure",
    "IntegrationImpactReason",
    "LiveExternalCoreSnapshot",
    "LiveRestoreAssessment",
    "LiveRestoreDisposition",
    "ManifestAdapter",
    "ProtocolAdmissionReceipt",
    "RegistryCapabilityDiscoveryIndex",
    "RegistryCoverageFinding",
    "RegistryCoverageReport",
    "RestorePreflightResult",
    "RevalidationAssessment",
    "RevalidationChallenge",
    "RevalidationCompletionReceipt",
    "RevalidationDisposition",
    "RevalidationEvidenceBinding",
    "RevalidationPlan",
    "RevalidationScope",
    "ScopedEvidenceRecord",
    "ScopedRevalidationAssessment",
    "ScopedRevalidationEvidenceBinding",
    "TraceDiagnostic",
    "TraceNode",
    "TraceNodeStatus",
    "TraceSupersessionReceipt",
    "admit_authority_graph_state",
    "admit_handoff_state",
    "admit_manifest_state",
    "admit_work_trace_state",
    "artifact_state_digest",
    "assess_live_restore",
    "assess_live_restore_state",
    "assess_revalidation",
    "assess_scoped_revalidation",
    "audit_external_core",
    "audit_live_external_core",
    "build_canonical_admission_bundle",
    "build_canonical_admission_context",
    "build_integration_impact_closure",
    "build_revalidation_challenges",
    "build_revalidation_plan",
    "build_revalidation_scope",
    "canonical_frontier_digest",
    "challenge_subject_digest",
    "handoff_frontier_digest",
    "preflight_restore",
    "qualify_component_evolution",
    "run_canonical_admission_audit",
    "source_state_frontier_digest",
    "validate_handoff_for_consumer",
    "work_trace_frontier_digest",
)
