# External Core A3 — Canonical Registry & Live Coherence

Date: 2026-09-05
Status: approved for implementation
Base: post-A2 External Core Coherence Fabric

## Purpose

A2 defines strong component contracts, authority graph validation, typed handoffs, work traces, restore preflight, and read-only coherence audit. A3 closes the next structural gap: the fabric must be bound to the canonical External Core components and to a deterministic live frontier rather than relying on a representative caller-assembled profile.

A3 remains authority-neutral. It describes, binds, validates, discovers, audits, and refuses incoherent composition. It never verifies claims, assures subjects, authorizes actions, promotes learning, executes work, releases software, deploys systems, or mutates another family's canonical state.

## Governing law

> Registration proves identity and declared compatibility; registration never creates authority.

A3 is not family H, a global governor, an orchestrator, an invoker, or a repair service.

## Architecture

### 1. Federated manifest adapters

Canonical component identity remains owned by the existing A–G component implementation. A `ManifestAdapter` binds a stable adapter id and source locator to the component's canonical `COMPONENT_ID` and `COMPONENT_VERSION`, plus the A2 semantic manifest. The adapter is immutable and content-addressed.

The A3 builder reads identity/version from the canonical component objects at build time. A semantic adapter therefore cannot silently substitute a handwritten component version.

### 2. Canonical component registry

`CanonicalComponentRegistry` is an immutable, content-addressed set of adapters and manifests. It rejects duplicate component ids, duplicate adapter ids, identity/version mismatch between adapter and manifest, and non-canonical restore state.

The registry exposes read-only lookup and deterministic coverage validation. No registration operation is a capability grant.

### 3. Coverage closure

Coverage validation reports categorical findings for missing adapters, orphan adapters/manifests, duplicate semantic identity, identity drift, version drift, manifest drift, and source locator drift where applicable. Findings are deterministic and audit-only.

### 4. Live fabric snapshot

`LiveExternalCoreSnapshot` binds:

- registry digest,
- authority graph digest,
- artifact graph digest,
- handoff frontier digest,
- work-trace frontier digest,
- source-state frontier digest,
- exact component versions.

All frontier digests are deterministic over canonical state. The snapshot is content-addressed and exact-restorable.

### 5. Restore classification

A3 restore assessment is categorical:

- `CURRENT`: exact current registry, graph, frontiers, and component versions.
- `REQUIRES_REVALIDATION`: structurally valid historical state whose registry/version/topology no longer exactly matches current canonical state.
- `QUARANTINED`: tampered, internally inconsistent, or cryptographically invalid state.
- `UNKNOWN`: required current proof is unavailable.

These are structural restore dispositions, not Truth, Assurance, authorization, or release decisions.

### 6. Live coherence audit

The A3 audit is driven by a canonical registry and explicit live frontiers. It validates registry/graph coverage, handoff/work-trace linkage, current source/evidence/artifact state when supplied, and exact snapshot coherence. Empty runtime frontiers, when legitimate, are represented by deterministic empty-frontier digests rather than being silently omitted.

### 7. Capability catalog binding

A content-addressed `CapabilityCatalogBindingReceipt` binds the organizational capability catalog version/digest to a registry digest for descriptive provenance only. The receipt has an invariant `descriptive_only=True`. It cannot translate agent metadata authorities into component authority capabilities and cannot mint authorization or invocation rights.

### 8. Read-only discovery v2

Discovery may enumerate canonical components and contract providers/consumers from the registry. It exposes no invoke, execute, authorize, promote, register-at-runtime, repair, or mutation API.

## Canonical adapter population

A3 initially promotes the post-A2 interoperability profile into an explicit canonical adapter population covering the representative semantic authorities already used by the canonical audit across A–G. Identity and version are read dynamically from the canonical component classes. This is a canonical interoperability registry, not a claim that every Python module or every one of the 75 organization metadata entries is an independent External Core authority.

Future components must be added through an explicit adapter plus coverage test rather than silently appearing in audit topology.

## Fail-closed adversarial requirements

A3 tests must reject or surface:

- missing registration,
- orphan adapter/manifest,
- stale adapter version,
- component identity substitution,
- duplicate semantic component,
- non-canonical serialized state,
- forged capability binding that claims authority,
- registry rollback or substitution,
- mixed-version restore,
- authority graph/registry drift,
- handoff frontier tamper,
- work-trace frontier tamper,
- source-state frontier tamper,
- orphan handoff/trace lineage,
- authority laundering through registry declarations.

## Compatibility

`build_canonical_fabric_profile()` remains as a compatibility bridge but is derived from the canonical A3 registry. Existing A2 public APIs remain valid. A3 adds structural/read-only APIs without moving canonical authority out of A–G families.

## Acceptance

A3 is complete only when:

1. RED tests demonstrate the missing registry/live-coherence behavior.
2. Production implementation passes all A3 tests.
3. Existing A2/G and prior Assurance regressions remain green.
4. Canonical audit CLI is read-only and reports a clean registry-backed fabric.
5. Python 3.11 and 3.13 hosted CI both pass at the exact PR head.
6. Refoundation regression gate remains green at the exact PR head.
