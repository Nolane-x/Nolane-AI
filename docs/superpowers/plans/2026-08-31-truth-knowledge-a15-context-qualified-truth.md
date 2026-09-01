# A15 Context-Qualified Truth v9 — Implementation Plan

## Goal

Close the non-temporal applicability hole in Family-A truth closure without changing accepted v1–v8 semantics or creating a sixth authority.

## Task 1 — Canonical context and binding registries

RED first in `tests/test_truth_knowledge_hardening_wave15_context_registry.py`.

Implement:

- `nolane/external_core/knowledge_context_truth.py`
  - `TruthContext`
  - `ClaimContextBindingRevision`
  - `ClaimContextBindingRegistry`
- `nolane/external_core/evidence_context_truth.py`
  - `EvidenceContextBindingRevision`
  - `EvidenceContextBindingRegistry`

Contracts:

- explicit unique canonical qualifiers;
- exact entity/content-digest binding;
- strict revision 1 then +1;
- exact predecessor digest;
- no entity/digest rebind;
- explicit `global` projection for unbound legacy entities;
- relevant-only projection;
- deterministic restore with protocol/duplicate/gap/predecessor rejection;
- parent authority only, no `COMPONENT_ID`.

## Task 2 — Context-qualified epistemic scope

RED first in `tests/test_truth_knowledge_hardening_wave15_scope.py`.

Implement `nolane/external_core/epistemic_context_truth.py` and exact binding mode:

`context-dependence-defeasible-justification-provenance-lineage-temporal-v9`

Required semantics:

- explicit `TruthContext` is required;
- target mismatch => UNKNOWN + context debt;
- context mismatch excludes competitor from contradiction;
- same-context competitor retains existing cardinality semantics;
- mismatched evidence/parent/undercutter cannot affect the decision as if applicable;
- legacy global entities reproduce v8 applicability;
- relevant context projections bind scope and validation;
- unrelated binding changes do not stale scope.

Do not merely wrap an already-contradicted v8 disposition. Context must participate before the final v9 disposition is minted.

## Task 3 — Verification v9

RED first in `tests/test_truth_knowledge_hardening_wave15_verification.py`.

Implement `nolane/external_core/verification_context_truth.py`:

- dedicated v9 receipt/coverage/ledger types;
- exact v9 scope/context binding;
- preserve v8 common-basis component collapse;
- preserve controller-root and decision-origin exclusions;
- negative receipts retained;
- missing/stale context metadata fails closed;
- v8 receipt cannot masquerade as v9.

## Task 4 — Assurance v9

RED first in `tests/test_truth_knowledge_hardening_wave15_assurance.py`.

Implement `nolane/external_core/assurance_context_truth.py`:

- dedicated v9 closure certificate/gate;
- preserve A14 LOW/STANDARD/HIGH/CRITICAL thresholds and dependence rules;
- block closure for target-context mismatch or live context debt;
- use only context-valid live supported lineage for closure vetoes;
- bind exact v9 scope and verification coverage;
- certificate live recomputation;
- v8 certificate cannot masquerade as v9.

## Task 5 — Compatibility and authority hardening

Add:

- `tests/test_truth_knowledge_hardening_wave15_compatibility.py`
- `tests/test_truth_knowledge_hardening_wave15_authority.py`
- focused regressions for dead branch, unrelated staleness, restore attacks, and protocol separation.

No bindings + empty `TruthContext` must reproduce v8 disposition/coverage/closure behavior.

## Task 6 — CI surface

Only after v9 sidecars exist, update `.github/workflows/truth-knowledge-a.yml`:

- add all five v9 sidecars to push/pull_request path filters;
- compile all five sidecars;
- rename compile step to A1–A15 v1–v9;
- retain `python -m pytest -q tests/test_truth_knowledge_*.py`;
- retain repository authority audit.

## Task 7 — Candidate freeze

Update `CURRENT/TRUTH_KNOWLEDGE.md` to record A15 as a candidate only, not accepted.

Fresh exact-head requirements:

- Python 3.11 Truth A GREEN;
- Python 3.13 Truth A GREEN;
- repository audit clean on both;
- intended A15 diff only.

## Task 8 — Latest-main integration

Because other Family waves run concurrently:

1. re-read current `main` immediately before integration;
2. use latest `main` tree as base;
3. overlay only exact blobs from the tested A15 candidate;
4. create an integrated commit whose parent is latest `main`;
5. verify `behind_by=0` and only intended A15 files differ;
6. run fresh Truth A on the integrated exact head.

Do not reuse stale CI from the pre-integration candidate.

## Task 9 — Production acceptance

- Open production PR.
- Verify exact head/base/synthetic merge SHA.
- Run full Refoundation merge-state on Python 3.11/3.13.
- Require Refoundation + Truth A + downstream + dossiers + audit + zero-loss + Neural R2.3 gates.
- Inspect exact intended diff and review surface.
- Re-read `main` immediately before merge.
- Merge with expected-head protection.
- Verify production merge parents and final main.

## Task 10 — Acceptance seal

From exact production merge:

- create separate seal branch;
- change only `CURRENT/TRUTH_KNOWLEDGE.md` from candidate to accepted and append exact acceptance evidence;
- require exactly one changed file;
- run Truth A and full Refoundation on seal synthetic merge;
- race guard current main;
- merge seal with expected-head protection;
- verify final merge parents, PR state, final `main`, canonical A1–A15 status, and post-merge integrity surface.
