# A9 Temporal Truth — Implementation Plan

**Goal:** add explicit deterministic temporal validity to family-A Truth while preserving the accepted A1–A8 implementation files and identities unchanged wherever possible.

**Base:** A8 merge `64d1ed5ad816e731068f0612db90c5b32288a465`.

**Branch:** `refoundation/truth-knowledge-a9-temporal-validity`.

## Architectural decision after first RED

The first RED head proved that A8 has no temporal interval/context/binding capability. A9 will not retrofit temporal fields into v1/v2 dataclasses. Instead it will use authority-bound sidecar subprotocols:

```text
shared deterministic time primitives
        temporal_truth.py
              │
     ┌────────┼────────┐
     ↓        ↓        ↓
Evidence   Knowledge  ...
 temporal   temporal
 sidecar    sidecar
     │        │
     └────┬───┘
          ↓
 Epistemic temporal scope
          ↓
 Verification temporal v3
          ↓
 Assurance temporal v3
```

This makes legacy compatibility structural rather than conditional: A1–A8 record/receipt/certificate classes do not need temporal fields at all.

## New modules

### `nolane/external_core/temporal_truth.py`
Pure deterministic primitives only:

- strict UTC RFC3339-second validation;
- `TruthInterval` half-open `[valid_from, valid_until)`;
- `TemporalContext` with explicit `as_of` and content digest;
- no `COMPONENT_ID`;
- no wall-clock calls.

### `nolane/external_core/evidence_temporal_truth.py`
`PARENT_COMPONENT_ID = "external.evidence"`.

- content-addressed `EvidenceTemporalBinding` binds one existing `TruthEvidence.content_digest` to a validity interval;
- `TemporalEvidenceView` owns only temporal bindings, not evidence history;
- unbound legacy evidence is timeless;
- state at context: `missing`, `revoked`, `binding_mismatch`, `not_yet_valid`, `expired`, `active`;
- scoped temporal projection/digest includes context and base evidence state.

### `nolane/external_core/knowledge_temporal_truth.py`
`PARENT_COMPONENT_ID = "external.knowledge"`.

- `KnowledgeTemporalBinding` binds one existing `KnowledgeClaim.content_digest` to an interval;
- `TemporalKnowledgeView` owns only applicability bindings;
- unbound legacy claim is timeless;
- temporal fixed-point competition includes only claims applicable at `as_of`;
- required parent lineage remains visible even when non-applicable so failure is auditable;
- scoped temporal projection/digest includes context and base claim state.

### `nolane/external_core/epistemic_temporal_truth.py`
`PARENT_COMPONENT_ID = "external.epistemic"`.

- `TemporalTruthDependencyScope` is a new v3 scope object;
- `TemporalEpistemicJudge` recursively evaluates lineage at explicit context;
- expired/not-yet-valid evidence cannot support;
- non-applicable historical competitors cannot create live contradiction;
- non-applicable required parent fails descendant support closed;
- live validation recomputes canonical v3 scope from all four source inputs.

### `nolane/external_core/verification_temporal_truth.py`
`PARENT_COMPONENT_ID = "external.verification"`.

- `TemporalTruthVerificationReceipt` uses binding mode `dependency-scope-temporal-v3`;
- receipt binds temporal scope digest + temporal context digest + canonical `as_of`;
- `TemporalTruthVerificationLedger` validates provenance against temporal evidence state at that exact context;
- separate ledger prevents accidental acceptance of v1/v2 receipts as temporal proof.

### `nolane/external_core/assurance_temporal_truth.py`
`PARENT_COMPONENT_ID = "external.assurance"`.

- `TemporalTruthClosureCertificate` v3 binds temporal scope, verification projection and context;
- `TemporalTruthAssuranceGate` reuses existing risk thresholds but requires temporal v3 verification;
- live validation recomputes the exact temporal closure and rejects a different `as_of`.

## Compatibility invariant

The following A1–A8 files should remain byte-identical unless a demonstrated integration requirement forces a minimal change:

- `evidence_truth.py`
- `knowledge_truth.py`
- `epistemic_truth.py`
- `verification_truth.py`
- `assurance_truth.py`

Legacy tests must stay GREEN without compatibility branches inside those classes.

## TDD sequence

1. First RED head: capability gap proof against A8 surface.
2. RED refinement: tests lock the sidecar interface while production remains absent.
3. GREEN: add only sidecar modules + focused workflow coverage.
4. Focused Truth GREEN Python 3.11/3.13.
5. Re-fetch/integrate current `main` without overwriting concurrent work.
6. Open PR and run full Refoundation Epoch 0 Python 3.11/3.13.
7. Only after integrated GREEN, update canonical `CURRENT/TRUTH_KNOWLEDGE.md` to A1–A9 accepted.
8. Rerun focused + full exact final head.
9. Verify diff/mergeability/reviews and merge with expected head SHA.
10. Prove post-merge main tree equals tested final tree.

## Required semantic tests

- canonical context round-trip and malformed timestamp rejection;
- half-open interval boundary;
- expired evidence cannot support;
- non-overlapping historical claims do not conflict;
- parent outside validity window fails descendant support;
- temporal verification receipt cannot be reused at another context;
- temporal assurance certificate cannot validate at another context;
- revocation still invalidates temporal certificate;
- forged binding/content digest fails closed;
- all six new modules expose no `COMPONENT_ID`;
- legacy Evidence/Knowledge/v1/v2 Verification/Assurance state remains temporal-key-free.

## Focused workflow

Update `.github/workflows/truth-knowledge-a.yml` so all six A9 sidecar modules are in both path filters and the compile list. This ensures future sidecar-only changes cannot bypass family-A CI.

## Full acceptance

Exact final head must pass:

- Truth Knowledge A Layer 3.11 + 3.13;
- Refoundation Epoch 0 3.11 + 3.13;
- 67/67 dossier freshness;
- quarantine audit;
- zero-loss evidence;
- organization/campaign/execution regressions;
- frozen Neural R2.3;
- clean PR authority/review surface.
