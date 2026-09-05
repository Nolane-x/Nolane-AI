# External Core Component-Local Version Discipline & Integration Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository's existing component-local `0.0.N` version law machine-enforced and evolve only `external.integration` to v0.0.2 with proof-carrying compatibility/impact/revalidation semantics.

**Architecture:** A read-only metadata gate derives component ownership from source/import structure and compares base/head revision maps. Separately, immutable integration-evolution primitives extend the existing `external.integration` authority without creating a new platform component or global version.

**Tech Stack:** Python 3.11/3.13, stdlib `ast`, `subprocess`, dataclasses/enums, canonical digest utilities, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-05-external-core-version-discipline-integration-evolution-design.md`

## Global Constraints

- Preserve canonical component-local version grammar `0.0.N`.
- No global External Core version or A4/A5 current-version label.
- Only `external.integration` advances from `0.0.1` to `0.0.2` in semantic component revisions.
- Version Discipline is read-only tooling and gets no component identity/version.
- Existing A–G authority boundaries remain unchanged; no family H/global governor.
- No auto version repair, migration, authorization, promotion, Assurance, execution, release or deployment path.
- Historical v1/A2/A3 states remain compatible; do not refreeze historical release locks.
- All production behavior is TDD: failing contract first, then minimum implementation.

---

### Task 1: Version Discipline pure contracts

**Files:**
- Create: `tests/test_external_core_version_discipline.py`
- Create after RED: `nolane/metadata/version_discipline.py`

**Interfaces:**
- Produces `VersionDisciplineFinding`, `VersionDisciplineReport`, `evaluate_revision_delta(base_revisions, head_revisions, affected_components, new_component_roots=())`.

- [ ] Write RED tests proving unchanged revision after semantic change, unrelated bump, jump, downgrade, new component above zero, exact +1 success, and deterministic finding ordering.
- [ ] Run `python -m pytest -q tests/test_external_core_version_discipline.py`; expected failure because module/API is absent.
- [ ] Implement immutable finding/report types and pure revision-delta evaluator with stable codes from the spec.
- [ ] Re-run focused tests; expected all pass.
- [ ] Commit tests + minimal implementation.

### Task 2: Source/import ownership discovery

**Files:**
- Modify: `tests/test_external_core_version_discipline.py`
- Modify: `nolane/metadata/version_discipline.py`

**Interfaces:**
- Produces `discover_component_ownership(source_by_module: Mapping[str, str], changed_modules: Collection[str], component_ids: Collection[str]) -> Mapping[str, tuple[str, ...]]`.

- [ ] Add RED tests with in-memory module sources: direct `COMPONENT_ID`, one-hop helper, transitive helper, shared helper reaching two components, unrelated structural module, invalid duplicate component root.
- [ ] Run focused tests and verify the new ownership tests fail for missing behavior.
- [ ] Implement AST literal component-root discovery and canonical `nolane.*` import graph traversal; no execution/import of source under analysis.
- [ ] Re-run focused tests; expected pass.
- [ ] Commit.

### Task 3: Git base/head checker and CLI

**Files:**
- Modify: `tests/test_external_core_version_discipline.py`
- Modify: `nolane/metadata/version_discipline.py`
- Create: `nolane/metadata/version_discipline_cli.py`

**Interfaces:**
- Produces `check_git_revision_discipline(repo_root: Path, base_ref: str, head_ref: str) -> VersionDisciplineReport` and CLI `python -m nolane.metadata.version_discipline_cli --base ... --head ... [--check] [--json]`.

- [ ] Add RED tests using a temporary Git repository with a minimal `COMPONENT_SPECS`, revision map and component modules. Lock clean +1, missing bump, unrelated bump and shared-helper behavior.
- [ ] Verify RED.
- [ ] Implement safe `git diff --name-only`, `git ls-tree`, `git show` readers, AST revision-map parsing, canonical module collection, ownership derivation and report generation. Reject malformed/nonliteral revision declarations rather than executing them.
- [ ] Implement deterministic text and JSON CLI output; `--check` exits 1 on blocking findings.
- [ ] Run focused tests; expected pass.
- [ ] Commit.

### Task 4: CI enforcement wiring

**Files:**
- Modify: `.github/workflows/external-core-a2.yml`
- Modify: `tests/test_external_core_version_discipline.py`

**Interfaces:**
- Workflow name becomes `External Core`.
- PR checkout must provide enough Git history for base/head comparison.

- [ ] Add a contract test that loads workflow text and requires generic workflow naming, version-discipline test inclusion, and gate invocation with PR base/head variables.
- [ ] Verify RED against the current A2+A3 workflow.
- [ ] Update workflow: include `tests/test_external_core_version_discipline.py`, run the focused version contracts, then execute version-discipline CLI on PR events; retain Python 3.11/3.13 A2/A3/G/audit/regression steps.
- [ ] Ensure push/local workflow paths do not fabricate a base ref; on non-PR event run tests but skip diff gate unless refs are explicitly available.
- [ ] Re-run workflow-contract tests.
- [ ] Commit.

### Task 5: Integration evolution immutable delta + compatibility qualification

**Files:**
- Create: `tests/test_external_core_integration_evolution.py`
- Create after RED: `nolane/external_core/integration_evolution.py`

**Interfaces:**
- `ComponentEvolutionDelta.create(old_manifest, new_manifest)`
- `EvolutionCompatibilityDisposition`
- `EvolutionCompatibilityQualification.qualify(delta)`

- [ ] Write RED tests for exact no-change, version-only revalidation, removed contract incompatibility, authority/resource incompatibility, identity mismatch, exact restore/tamper rejection, strict string input and direct-constructor forgery rejection at qualification.
- [ ] Verify RED due missing module/API.
- [ ] Implement content-addressed delta state, deterministic changed-field rows, strict integrity validation and categorical qualification.
- [ ] Re-run focused tests.
- [ ] Commit.

### Task 6: Deterministic integration impact closure

**Files:**
- Modify: `tests/test_external_core_integration_evolution.py`
- Modify: `nolane/external_core/integration_evolution.py`

**Interfaces:**
- `build_integration_impact_closure(changed_component_ids, authority_graph, handoffs=(), traces=()) -> IntegrationImpactClosure`.

- [ ] Add RED tests for transitive authority/contract component impact, handoff producer/consumer impact, predecessor handoff propagation, trace component/handoff binding propagation, deterministic reason edges, and forged closure restore rejection.
- [ ] Verify RED.
- [ ] Implement monotonic fixed-point closure over supplied structural state only; no invocation/mutation.
- [ ] Re-run focused tests.
- [ ] Commit.

### Task 7: External revalidation receipts and transition assessment

**Files:**
- Modify: `tests/test_external_core_integration_evolution.py`
- Modify: `nolane/external_core/integration_evolution.py`

**Interfaces:**
- `IntegrationRevalidationReceipt.create(...)`
- `assess_integration_transition(...) -> IntegrationTransitionAssessment`
- transition dispositions: `CURRENT`, `REVALIDATION_REQUIRED`, `INCOMPATIBLE`, `UNKNOWN`, `QUARANTINED`.

- [ ] Add RED tests for self-verifier rejection, positive result without evidence rejection, duplicate evidence ref rejection, snapshot substitution, uncovered delta/impact resulting in revalidation-required, incompatibility dominance, unknown missing state, fully covered current transition, and forged direct constructor quarantine.
- [ ] Verify RED.
- [ ] Implement exact old/new live snapshot binding, evidence digest bindings, distinct verifier rule, coverage accounting and categorical transition assessment.
- [ ] Re-run focused tests.
- [ ] Commit.

### Task 8: Component-local version advancement and public contract

**Files:**
- Modify: `nolane/external_core/integration.py`
- Modify: `nolane/external_core/compatibility.py`
- Modify: `nolane/metadata/component_versions.py`
- Modify: `tests/test_refoundation_component_versions.py`
- Create: `tests/test_external_core_integration_evolution_public_contract.py`
- Modify: `nolane/external_core/__init__.py`

**Interfaces:**
- `external.integration` exactly `0.0.2`.
- compatibility semantic surface exactly `0.0.2`.
- public immutable/read-only evolution symbols exported; no control-authority verbs.

- [ ] Write RED tests requiring revision 2 and public exports while forbidding invoke/execute/authorize/promote/assure/repair/deploy/auto-migrate surfaces.
- [ ] Verify RED.
- [ ] Advance only `external.integration` revision slot from 1 to 2 and source constants to `0.0.2`; export safe structures/functions.
- [ ] Update accepted component revision fixture for integration only.
- [ ] Run focused version/public tests.
- [ ] Commit.

### Task 9: Canonical documentation and audit integration

**Files:**
- Modify: `CURRENT/EXTERNAL_CORE.md`
- Modify: `nolane/external_core/audit.py` only if a read-only evolution structural check is required by tests.
- Modify: `tests/test_external_core_integration_evolution.py`

**Interfaces:**
- Current docs state component-local version discipline and `external.integration` v0.0.2; no new aggregate platform version.

- [ ] Add RED documentation/audit contract tests for no current A4/global version language and for exact component-local ownership statements.
- [ ] Update current documentation and optional read-only audit finding integration without mutation/repair.
- [ ] Run focused tests + `python -m nolane.external_core.audit --check`.
- [ ] Commit.

### Task 10: Adversarial closure and full verification

**Files:**
- Create: `tests/test_external_core_version_discipline_adversarial.py`
- Create: `tests/test_external_core_integration_evolution_adversarial.py`
- Modify production only in response to observed RED failures.

**Interfaces:**
- Locks all adversarial cases in spec §8.

- [ ] Write adversarial tests first and capture genuine RED for any uncovered bypass.
- [ ] Harden only the reproduced bypasses.
- [ ] Run all External Core tests, component-version tests and G/Assurance regressions.
- [ ] Run canonical audit with `--check` and `--json`.
- [ ] Run Python compile checks.
- [ ] Open PR against `main` and obtain exact merge-ref CI on Python 3.11/3.13 plus relevant Refoundation gate.
- [ ] Review PR diff for authority widening, accidental global-version language, unrelated revision bumps and historical lock edits.
- [ ] Mark Ready only after exact-head gates are green. Do not merge without a later explicit user merge authorization.
