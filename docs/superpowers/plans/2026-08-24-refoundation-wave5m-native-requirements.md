# Refoundation Epoch 0 Wave 5M — Native Requirements Implementation Plan

> Execute on `refoundation/epoch0-wave5m-native-requirements`. Do not modify `main`; do not auto-merge.

**Goal:** move `external.requirements` from compatibility-facade ownership to canonical native authority at `nolane.external_core.requirements` with zero semantic loss.

**Exact parent:** `69554e6cf963824e4ce7dd9034b168cecad6a1a3`

**Design:** `docs/superpowers/specs/2026-08-24-refoundation-wave5m-native-requirements-design.md`

---

## Task 1 — Freeze and forensic boundary

1. Confirm exact parent/head lineage.
2. Read:
   - `cogcoder/organization/requirements.py`;
   - `nolane/external_core/requirements.py`;
   - active facade registry;
   - component version map;
   - implementation-status ledger;
   - generated native debt;
   - existing Requirements/Planning/organization tests that exercise this surface.
3. Record exclusions: Planning, Architecture, TaskGraph/lease reconciliation, event redesign, historical moves.

**Stop if:** Requirements semantics depend on an unreviewed hidden writer or persistence format not represented by the frozen boundary.

## Task 2 — TDD RED native-ownership/parity contracts

Create `tests/test_refoundation_wave5m_native_requirements.py` before production cutover.

RED contracts must cover:

- canonical symbol implementation ownership is native, not historical;
- legacy module re-exports exact canonical public objects;
- enum values and state round-trip;
- criterion/node validation;
- deterministic graph ordering and digest;
- unknown-dependency and cycle rejection;
- evidence/reason/non-empty mutation requirements;
- revision sequence and state restoration integrity;
- authorized and unauthorized control-plane writes;
- ambiguity/change/acceptance-gap proposal event semantics;
- component revision/native-ledger/facade/debt expectations.

Run the focused test and confirm it fails for the intended pre-cutover reasons.

## Task 3 — Move executable authority to canonical Requirements

Replace `nolane/external_core/requirements.py` facade implementation with the reviewed Requirements semantics currently owned by `cogcoder.organization.requirements`.

Rules:

- preserve public API names and serialized values;
- preserve canonical digest semantics;
- preserve EventKind compatibility aliases;
- preserve registry/authority/ledger interaction;
- do not import Planning/Architecture;
- set `COMPONENT_VERSION = "0.0.1"`;
- retain `MIGRATED_FROM = "cogcoder.organization.requirements"` as provenance metadata.

## Task 4 — Convert historical source to exact bridge

Replace executable ownership in `cogcoder/organization/requirements.py` with an explicit compatibility re-export from `nolane.external_core.requirements`.

Require exact public-object identity across canonical and legacy imports.

No deletion or move.

## Task 5 — Advance component-local authority bookkeeping

Update only the required source-of-truth bookkeeping:

- `cogcoder/refoundation/component_versions.py`: `external.requirements` revision `0 → 1`;
- `cogcoder/refoundation/implementation_status.py`: `external.requirements` becomes canonical-native with write authority and canonical module ownership;
- `cogcoder/refoundation/facades.py`: remove active Requirements facade binding;
- cross-wave acceptance tests: add Requirements to accepted native/revision-one sets and remove it from the explicit facade sentinel set while preserving Context/Planning/Architecture sentinels.

Do not bump unrelated components.

## Task 6 — Focused GREEN and parity verification

Run/verify:

- Wave 5M native Requirements tests;
- component-version tests;
- implementation-status tests;
- active-facade parity tests;
- relevant organization Requirements/Planning regressions;
- repository audit tests.

Fix only evidence-backed regressions; do not weaken invariants.

## Task 7 — Regenerate native debt from audit

Use the repository's approved audit-generation path to refresh `CURRENT/NATIVE_DEBT.json` and `CURRENT/NATIVE_DEBT.md`.

Expected transition:

`33 → 32`

`external.requirements` must disappear from generated debt. Neighboring components remain unchanged.

Generated debt files are outputs, not hand-authored architecture claims.

## Task 8 — Cleanup guard

Add `tests/test_refoundation_wave5m_bootstrap_cleanup.py` or equivalent final-head protection proving no temporary Wave-5M bootstrap/carrier branch/workflow remains.

Remove all temporary authority carriers before final verification.

## Task 9 — Full exact-head hosted acceptance

Push the exact post-cleanup head and require GitHub Actions success on Python 3.11 and 3.13 for:

- compile accepted/canonical namespaces;
- 67 resolved AI dossier freshness;
- repository audit freshness;
- full Refoundation contracts;
- zero-loss evidence generation/upload;
- organization/campaign/execution regressions;
- frozen Neural R2.3 metadata contracts.

If any code/docs/test commit changes the source head after a green run, that run is stale and cannot be final evidence.

## Task 10 — Acceptance receipt and PR state

Only after exact-head green:

1. capture exact head SHA;
2. capture hosted run ID;
3. capture both artifact IDs and SHA-256 digests;
4. record debt `33 → 32`;
5. record historical disposition and cleanup state;
6. update PR metadata with the acceptance receipt without changing source head;
7. mark Ready for Review;
8. do not auto-merge.

## Definition of Done

Wave 5M is complete only when:

- canonical Requirements owns the implementation;
- legacy Requirements is an exact bridge;
- all frozen behavior/state/authority/event contracts are preserved;
- only `external.requirements` advances to `0.0.1`;
- Requirements leaves facade/native-debt classifications;
- native debt is generated as 32;
- no historical bytes are destroyed;
- no temporary bootstrap authority remains;
- exact-head Python 3.11 and 3.13 hosted matrices are fully green;
- PR is Ready for Review with immutable acceptance evidence and no auto-merge.
