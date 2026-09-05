"""Canonical extra-neural cognition and engineering substrate namespace.

The conceptual External Core is intentionally wider than the invokable
ExternalCoreRegistry: it also contains persistent memory, context, planning,
architecture, evidence-backed engineering and other governed cognition.

The A2 exports below are deliberately structural and authority-neutral. They
expose immutable contracts, validation, discovery, provenance and audit
surfaces; they do not expose an invocation path or mint runtime authority.
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
)
from nolane.external_core.coherence_audit import (
    CoherenceAuditReport,
    CoherenceFinding,
    ExternalCoreRestoreSnapshot,
    RestorePreflightResult,
    audit_external_core,
    preflight_restore,
)
from nolane.external_core.component_contracts import (
    ExternalComponentManifest,
    ExternalCoreFamily,
)
from nolane.external_core.handoff import (
    ExternalHandoffEnvelope,
    HandoffAuthorityClass,
    HandoffValidationDisposition,
    HandoffValidationResult,
    validate_handoff_for_consumer,
)
from nolane.external_core.work_trace import (
    CognitiveWorkTrace,
    TraceDiagnostic,
    TraceNode,
    TraceNodeStatus,
    TraceSupersessionReceipt,
)


__all__ = (
    "AuthorityEdge",
    "AuthorityGraphFinding",
    "AuthorityGraphValidationReport",
    "AuthorityRelation",
    "CapabilityDescriptor",
    "CapabilityDiscoveryIndex",
    "CognitiveWorkTrace",
    "CoherenceAuditReport",
    "CoherenceFinding",
    "ContractDiscoveryResult",
    "ExternalAuthorityGraph",
    "ExternalComponentManifest",
    "ExternalCoreFamily",
    "ExternalCoreRestoreSnapshot",
    "ExternalHandoffEnvelope",
    "HandoffAuthorityClass",
    "HandoffValidationDisposition",
    "HandoffValidationResult",
    "RestorePreflightResult",
    "TraceDiagnostic",
    "TraceNode",
    "TraceNodeStatus",
    "TraceSupersessionReceipt",
    "audit_external_core",
    "preflight_restore",
    "validate_handoff_for_consumer",
)
