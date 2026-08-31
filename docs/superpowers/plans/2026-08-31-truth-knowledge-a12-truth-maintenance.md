# A12 Truth Maintenance / Multiple Independent Justifications — Implementation Plan

## Goal

Implement v6 additive truth-maintenance semantics over accepted A1–A11 without changing historical protocols or canonical authority ownership.

## Task 1 — RED contract

Add A12 behavior, authority, and domain-separation tests before production modules exist. Required RED must prove the repository does not yet provide v6 justification truth maintenance.

## Task 2 — Knowledge justification sidecar

Create `nolane/external_core/knowledge_justification_truth.py` with:

- `KnowledgeJustificationBasis`;
- `KnowledgeJustificationRevision`;
- `KnowledgeJustificationRegistry`;
- implicit legacy basis projection;
- exact revision/predecessor/domain binding;
- duplicate-basis rejection;
- current effective dependency-cycle rejection;
- relevant-only projection and canonical digest;
- deterministic v6 lineage/evidence helpers.

No `COMPONENT_ID`.

## Task 3 — Epistemic v6

Create `nolane/external_core/epistemic_justification_truth.py` with:

- exact binding mode `justification-provenance-lineage-temporal-v6`;
- relation-aware temporal v6 fixed point using A12 lineage;
- independent evaluation of each effective justification;
- OR-of-AND aggregation that exposes contradictions;
- per-path audit statuses;
- relevant temporal/evidence/relation/justification/provenance bindings;
- source sets split into all relevant sources vs live supporting sources;
- canonical live validation.

## Task 4 — Verification v6

Create `nolane/external_core/verification_justification_truth.py` with dedicated v6 receipt/ledger/coverage. Preserve A11 provenance validation and negative receipts. Independence excludes root controllers of live supporting sources only.

## Task 5 — Assurance v6

Create `nolane/external_core/assurance_justification_truth.py` with unchanged risk thresholds and v6 live-recomputed certificates. Block unsupported/contradicted lineage, relation ambiguity, critical debt, incomplete provenance, invalid/negative verification, and diversity deficits.

## Task 6 — Workflow and canonical status

Update `.github/workflows/truth-knowledge-a.yml` path filters and compile list for all v6 sidecars. Mark CURRENT as `A1–A11 accepted; A12 candidate` with exact proof state, never accepted before full exact-head Refoundation passes.

## Task 7 — Verification and merge

1. focused Truth/Knowledge on Python 3.11 and 3.13;
2. repository audit;
3. exact-head full Refoundation Epoch 0 on Python 3.11 and 3.13;
4. inspect intended diff, mergeability, reviews and threads;
5. merge only with exact-head protection;
6. create doc-only acceptance seal from the merge commit;
7. verify seal and merge it so CURRENT becomes `A1–A12 accepted`.

## Concurrency rule

Other External Core families may advance `main` concurrently. Do not modify unrelated files. Re-check latest `main` and PR mergeability before merge; if integration state changes, verify the synthetic merge state rather than assuming branch-only CI is sufficient.
