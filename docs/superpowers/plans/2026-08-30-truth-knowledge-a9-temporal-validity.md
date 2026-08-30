# A9 Temporal Truth — Current Implementation / Acceptance Plan

**Goal:** close the last unaccepted family-A workstream by adding deterministic temporal validity on top of accepted A10 relation semantics without changing A1–A10 legacy identities.

**Current clean branch:** `refoundation/truth-knowledge-a9-temporal-validity-current`

**Construction base:** `main@393eff644305e79517f7d73b7f7208ffd9c2471c`

## Architectural correction

The historical A9 draft proposed `dependency-scope-temporal-v3`. That numbering became invalid when A10 Relation Semantics was accepted first and canonically occupied v3 with `relation-aware-scope-v3`.

A9 is therefore implemented as:

```text
A8 dependency-scope-v2
        ↓
A10 relation-aware-scope-v3
        ↓
A9 relation-aware-temporal-v4
```

No parallel v3 and no downgrade path are permitted.

## TDD evidence obtained

### Initial capability RED

Old A9 contracts were transplanted onto current `main` without old branch history. On exact test-only head, canonical A1–A10 remained healthy while A9 failed only because temporal modules did not exist.

### Corrected v4 RED

After rewriting the tests to inherit A10 semantics, run #87 on exact test-only head `0c659675ed6534558e128a37ae18fd0374e06033` produced:

- 90 existing Truth tests passing;
- 15 A9 tests failing;
- failures caused by missing `nolane.external_core.temporal_truth`, not unrelated regression.

### First GREEN

After implementing the six A9 sidecars and hardening Truth CI, run #88 showed on Python 3.11 and 3.13:

- sidecar compile success;
- 105/105 Truth contracts passing;
- repository authority audit success;
- no new canonical authority.

### Revision-lineage RED

A further design audit found that one immutable interval per evidence/claim could not represent newly learned expiry while retaining history. New RED tests required append-only temporal revisions.

Run #89 on Python 3.11 produced:

- 105 pre-existing tests passing;
- exactly 5 new revision-lineage tests failing;
- failures only at missing `revision`/`revise` API.

### Revision-lineage GREEN

Evidence and Knowledge temporal sidecars now use predecessor-bound append-only revisions. Focused Truth tests and authority audit returned GREEN again on both Python matrices before documentation staging.

## Implemented modules

### `temporal_truth.py`

- strict UTC RFC3339 seconds;
- `TruthInterval` half-open `[from, until)`;
- content-addressed `TemporalContext`;
- no wall-clock reads;
- no `COMPONENT_ID`.

### `evidence_temporal_truth.py`

- parent `external.evidence`;
- predecessor-bound `EvidenceTemporalBinding` revision lineage;
- current state: missing/revoked/mismatch/not-yet-valid/expired/active;
- relevant-only scoped temporal projection;
- unbound legacy evidence remains timeless.

### `knowledge_temporal_truth.py`

- parent `external.knowledge`;
- predecessor-bound `KnowledgeTemporalBinding` revision lineage;
- required parents remain visible even when not applicable;
- relation-aware v4 fixed point admits only applicable competitors;
- A10 multi-valued/unspecified/exclusive behavior retained.

### `epistemic_temporal_truth.py`

- parent `external.epistemic`;
- `TemporalTruthRelationAwareScope` v4;
- exact binding to Knowledge, Evidence, Relation Semantics, both temporal projections and `TemporalContext`;
- explicit temporal Epistemic debt;
- canonical live re-derivation.

### `verification_temporal_truth.py`

- parent `external.verification`;
- dedicated `TemporalTruthVerificationReceipt`;
- exact binding mode `relation-aware-temporal-v4`;
- context/scope replay blocked;
- live temporal provenance required;
- negative results retained;
- exact source-family/channel diversity.

### `assurance_temporal_truth.py`

- parent `external.assurance`;
- dedicated v4 certificate;
- existing LOW/STANDARD/HIGH/CRITICAL verification thresholds;
- live re-derivation of the full v4 closure;
- relevant temporal/relation/revocation changes stale authority;
- unrelated temporal changes remain scoped out.

## Compatibility constraints

The accepted files remain unchanged by A9 implementation:

- `evidence_truth.py`
- `knowledge_truth.py`
- `epistemic_truth.py`
- `verification_truth.py`
- `assurance_truth.py`
- `nolane/memory/knowledge.py`
- `nolane/metadata/subprotocols.py`

A9 does not modify legacy v1/v2/v3 record shapes and does not bump canonical parent component revisions.

## CI hardening

`.github/workflows/truth-knowledge-a.yml` now:

- watches all six A9 sidecar paths;
- compiles them on Python 3.11 and 3.13;
- runs all `tests/test_truth_knowledge_*.py`;
- runs repository authority audit.

## Remaining acceptance sequence

1. Stage `CURRENT/TRUTH_KNOWLEDGE.md` as **A9 final candidate**, not accepted.
2. Re-fetch current `main` and compare all A9 paths against concurrent merges.
3. If `main` drifted, build a clean integration candidate from latest `main`; never merge stale branch history.
4. Run focused Truth 3.11/3.13 on exact integrated head.
5. Open A9 PR only after clean scope verification.
6. Run PR-triggered full Refoundation Epoch 0 3.11/3.13.
7. Inspect any failure with systematic debugging; do not weaken tests/gates.
8. Verify PR reviews/comments/diff/mergeability.
9. Add acceptance seal only after all exact-head gates are green.
10. Rerun full gate if acceptance seal changes the head.
11. Merge with `expected_head_sha`.
12. Prove post-merge `main` contains the tested tree semantics.
13. Only then mark family A A1–A10 accepted in canonical documentation.

## Exact acceptance surface

Before merge, exact final head must prove:

- all Truth tests on Python 3.11/3.13;
- repository audit: no duplicate authority/new migration/reference debt;
- Refoundation Epoch 0 Python 3.11/3.13;
- 67/67 dossier freshness;
- zero-loss evidence generation;
- organization/campaign/execution regressions;
- frozen Neural R2.3;
- intended-only diff;
- no unresolved blocking review surface.

Post-merge proof is mandatory; a green pre-merge branch alone does not make A9 accepted.
