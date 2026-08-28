# Refoundation Executable Debt Closure Implementation Plan

> Execution rule: `CURRENT/` remains architectural authority. This plan is implementation guidance, not a higher-precedence architecture source.

**Goal:** Retire the final executable compatibility facades in the A1 Refoundation lineage without reviving historical-only capabilities or modifying the frozen Neural R2.3 asset authority.

**Architecture:** Complete three bounded waves after accepted Wave 5AO. Wave 5AP moves the complete Operations semantic closure under canonical `nolane.external_core` ownership. Wave 5AQ moves the complete Research semantic closure under canonical `nolane.external_core` ownership. Wave 5AR then proves executable-debt closure, canonical import direction, generated-audit freshness, compatibility-bridge exactness, and Refoundation workflow isolation. Historical `cogcoder.organization` modules become exact semantic bridges only after parity is locked by RED tests.

**Tech stack:** Python 3.11/3.13, pytest, GitHub Actions, `nolane.repository.audit`, `nolane.ai.materialize`, canonical SHA-256 digest/state contracts, frozen Neural R2.3 verifier.

---

## Task 1 — Wave 5AP RED: Native Operations authority contract

**Files:**
- Create: `tests/test_refoundation_wave5ap_native_operations.py`
- Preserve: existing Coding AGI ops tests as behavior oracles.

**RED contract:**
1. Assert `nolane.external_core.operations` and the Operations helper modules own their public classes (`__module__` under `nolane.external_core`) rather than reverse-importing executable `cogcoder.organization` implementations.
2. Assert legacy Operations imports are exact-object bridges to canonical public objects.
3. Assert canonical Operations source contains no `cogcoder.organization` dependency.
4. Assert the semantic closure includes Operations profiles, data migration, infrastructure/release, reliability/performance, assurance-gated readiness, deterministic digest/state restoration, and regional permission enforcement.
5. Assert `external.operations` becomes `canonical_native`, version `0.0.1`, and generated native debt moves from 8 to 7.

Observe hosted RED before production migration.

## Task 2 — Wave 5AP GREEN: Move Operations semantic closure

**Files:**
- Modify: `nolane/external_core/operations.py`
- Create: `nolane/external_core/operations_profiles.py`
- Create: `nolane/external_core/data_operations.py`
- Create: `nolane/external_core/infrastructure_operations.py`
- Create: `nolane/external_core/reliability_operations.py`
- Modify historical Operations modules into exact semantic compatibility bridges.
- Update implementation/version authority and `CURRENT/STATUS.md` through a verified authority carrier.
- Regenerate `CURRENT/NATIVE_DEBT.json`, `CURRENT/NATIVE_DEBT.md`, and `archive/INDEX.json` with `nolane.repository.audit --write`.

**Canonical dependencies:** artifacts, assurance, skills/evolution, identity registry, and canonical digest must resolve through `nolane` authorities only.

**Verification:**
- `python -m compileall -q cogcoder/organization cogcoder/refoundation nolane`
- `python -m nolane.ai.materialize --check`
- `python -m nolane.repository.audit --check`
- `python -m pytest -q tests/test_refoundation_*.py`
- `python -m pytest -q tests/test_coding_agi_ops_*.py tests/test_coding_agi_assurance_*.py tests/test_coding_agi_evolution_*.py tests/test_coding_agi_foundation_*.py`
- `python model/neural-r2.3/scripts/verify_neural_r23.py`

## Task 3 — Wave 5AQ RED/GREEN: Native Research authority

**Files:**
- Create: `tests/test_refoundation_wave5aq_native_research.py`
- Modify: `nolane/external_core/research.py`
- Create: `nolane/external_core/research_profiles.py`
- Create: `nolane/external_core/research_provenance.py`
- Convert historical `research.py`, `research_profiles.py`, and `research_provenance.py` into exact semantic bridges.
- Update implementation/version/status authority through a verified carrier and regenerate repository audit projections.

**RED/GREEN invariants:**
1. Exactly four Research identities remain authoritative: chief, repository archaeology, docs/API, prior art.
2. Routing remains deterministic and preserves primary-domain/domain/signal/availability scoring semantics.
3. Source quality, logical freshness, provenance requirements, contradiction assessment/resolution, and domain authorization remain fail-closed inside canonical `research_provenance` ownership.
4. Research synthesis/handoff, provenance state, and digests round-trip exactly.
5. Canonical Research implementation has no reverse `cogcoder.organization` import across any of the three modules.
6. `external.research` becomes `canonical_native`, version `0.0.1`, and generated native debt moves from 7 to 6.

**Verification:** full Refoundation contracts plus all research/assurance/context/evidence regressions and Neural R2.3 metadata verification.

## Task 4 — Wave 5AR: Executable-debt closure and stabilization

**Files:**
- Create: `tests/test_refoundation_wave5ar_executable_debt_closure.py`
- Update: `CURRENT/STATUS.md` with closure receipt.
- Harden Refoundation workflow routing only where a failing contract demonstrates runner leakage.

**Closure invariants:**
1. Generated debt contains exactly six intentional records: five `historical_only` semantic reservations plus `neural.shared` as `frozen_asset`.
2. Zero `compatibility_facade` and zero `legacy_internal` records remain.
3. No canonical `nolane` implementation reverse-imports executable authority from `cogcoder.organization` within authority clusters already claimed as fully native.
4. Historical bridge modules retain exact public-object identity where accepted compatibility is required.
5. 67 AI dossiers and generated repository audit projections are fresh.
6. Frozen Neural R2.3 contracts remain unchanged and verified.
7. Refoundation PR routing does not run legacy heavyweight workflows as active work on user-authored `refoundation/*` PR heads; bot receipt pushes may be `action_required` and are treated separately from hosted carrier evidence.

**Final verification:**
- compileall
- `nolane.ai.materialize --check`
- `nolane.repository.audit --check`
- all `tests/test_refoundation_*.py`
- broad Coding AGI organization/campaign/execution/evaluation/foundry/coordination/evolution/memory/context/research/ops/assurance/UI/debug/coding/foundation/central/requirements/planning/architecture/integration regressions
- Neural R2.3 verifier

Only after fresh hosted GREEN evidence may each wave be merged into `main`.