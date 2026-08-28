# Refoundation Wave 5AH Native Evaluation Parameters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `evaluation.parameters` semantic implementation authority from `cogcoder.organization.evaluation_parameters` to canonical `nolane.evaluation.parameters` without changing accepted behavior, while reducing native debt from 16 to 15 records.

**Architecture:** Preserve the accepted parameter-accounting/scaling algorithms byte-for-byte in semantics while relocating executable ownership into the canonical evaluation package. Canonical code will resolve evidence, regime provenance, organization identity, and digest dependencies only through `nolane` authorities; the historical module becomes an exact-object compatibility bridge. Refoundation version, implementation-ledger, facade, current-status, and generated debt projections move in the same acceptance wave.

**Tech Stack:** Python 3.11/3.13, dataclasses/enums, pytest, GitHub Actions, Nolane Refoundation component-version/implementation-ledger/repository-audit machinery.

**Spec:** `CURRENT/REPOSITORY_AUTHORITY.md` and the accepted Wave 5AG state at `fd231da72ddbe95d350dcbef6ace86159f748bbd`.

## Global Constraints

- Start from exact Wave 5AG GREEN head `fd231da72ddbe95d350dcbef6ace86159f748bbd`.
- Establish and host a deliberately RED Wave 5AH contract before changing production ownership.
- `evaluation.parameters` advances only from `0.0.0` to `0.0.1`; unrelated component revisions do not move.
- `nolane.evaluation.parameters` must contain no reverse import whose module starts with `cogcoder.organization`.
- Historical `cogcoder.organization.evaluation_parameters` public objects must be the exact same Python objects as canonical public objects.
- Preserve accepted parameter-footprint validation, scaling-proposal validation, decision gating, deterministic digest/state semantics, and state round-trip behavior.
- Retire only the active `evaluation.parameters` facade; do not cut over `evaluation.stress`, `evaluation.release`, `evaluation.claims`, `evaluation.scaling`, or `evaluation.campaign` in this wave.
- Generated `CURRENT/NATIVE_DEBT.json` and `.md` must report exactly 15 non-native records after the cutover.
- Historical predecessor receipts must remain monotonic: Wave 5AG continues proving its own cutover without forbidding later debt reduction.
- Final completion requires fresh exact-head `Nolane-AI Refoundation Epoch 0` success on both Python 3.11 and Python 3.13.

---

### Task 1: Establish the Wave 5AH RED contract

**Files:**
- Create: `tests/test_refoundation_wave5ah_native_evaluation_parameters.py`
- Modify only if needed for monotonicity after GREEN: `tests/test_refoundation_wave5ag_native_evaluation_evidence.py`

**Interfaces:**
- Consumes: `component_version()`, `build_active_facade_bindings()`, `build_component_implementation_ledger()`, `AgentRegistry`, `BenchmarkRegimeRegistry`, `EvaluationEvidenceLedger`.
- Produces: a contract that locks canonical ownership, exact historical identity, canonical-only imports, representative footprint/state behavior, native implementation authority, facade retirement, debt count 15, and Wave 5AH status receipt.

- [ ] **Step 1: Write the failing ownership/authority contract**

Use public symbols:

```python
_PUBLIC_SYMBOLS = (
    "ParameterFootprintReport",
    "ScalingDecision",
    "ScalingProposal",
    "ScalingDecisionReceipt",
    "ParameterScalingAuthority",
)
```

Assert canonical metadata is `evaluation.parameters` / `0.0.1` / `cogcoder.organization.evaluation_parameters`, all public symbols have `__module__ == "nolane.evaluation.parameters"`, legacy symbols are exact canonical identities, canonical imports include `nolane.evaluation.evidence`, `nolane.evaluation.regimes`, `nolane.organization.identity`, and `nolane.core.canonical_digest`, and no canonical import starts with `cogcoder.organization`.

- [ ] **Step 2: Add representative behavior parity**

Construct two canonical `AgentIdentity` values sharing one physical substrate, an `AgentRegistry`, an empty `BenchmarkRegimeRegistry`, an `EvaluationEvidenceLedger`, and a `ParameterScalingAuthority`. Call `parameter_footprint(...)`, assert shared/local/unique/logical arithmetic, serialize `to_state()`, restore with `ParameterScalingAuthority.from_state(...)`, and assert exact state/report equality.

- [ ] **Step 3: Add authority/debt/status assertions**

Assert implementation status `CANONICAL_NATIVE`, canonical write authority, version `0.0.1`, absence from active facade bindings, absence from `CURRENT/NATIVE_DEBT.json`, exact remaining count 15, and `CURRENT/STATUS.md` receipt containing `Wave 5AH`, `evaluation.parameters`, and `15 non-native`.

- [ ] **Step 4: Commit and host RED**

Commit only the new contract, open a draft PR from `refoundation/epoch0-wave5ah-native-evaluation-parameters` to `refoundation/epoch0-wave5ag-native-evaluation-evidence`, and inspect the fresh workflow logs. Production migration must not begin until the failures are confirmed to be the intended pre-cutover conditions while the Wave 5AG baseline remains green.

### Task 2: Move semantic ownership to `nolane.evaluation.parameters`

**Files:**
- Modify: `nolane/evaluation/parameters.py`

**Interfaces:**
- Consumes: `nolane.evaluation.evidence.EvaluationEvidenceLedger`, `nolane.evaluation.regimes.EvidenceProvenanceClass`, `nolane.organization.identity.AgentRegistry`, `nolane.core.canonical_digest.canonical_digest`.
- Produces: canonical `ParameterFootprintReport`, `ScalingDecision`, `ScalingProposal`, `ScalingDecisionReceipt`, and `ParameterScalingAuthority` at component version `0.0.1`.

- [ ] **Step 1: Copy the accepted implementation zero-loss**

Move the executable bodies from historical `cogcoder.organization.evaluation_parameters` into `nolane.evaluation.parameters`; do not redesign algorithms or validation gates.

- [ ] **Step 2: Retarget only dependency imports**

Use exactly the canonical dependency modules named in the Interfaces block and retain `from __future__ import annotations`, dataclass/enum/typing imports, all constants, validation rules, digest construction, idempotency behavior, getters, `to_state()`, and `from_state()` semantics.

- [ ] **Step 3: Set canonical migration metadata**

```python
COMPONENT_ID = "evaluation.parameters"
COMPONENT_VERSION = "0.0.1"
MIGRATED_FROM = "cogcoder.organization.evaluation_parameters"
```

- [ ] **Step 4: Run the focused contract after the semantic move**

Expected state: ownership/import/behavior assertions can turn GREEN, while authority/facade/debt/status assertions remain RED until the remaining tasks are completed.

### Task 3: Convert the historical implementation into an exact-object bridge

**Files:**
- Modify: `cogcoder/organization/evaluation_parameters.py`

**Interfaces:**
- Consumes: the five canonical public objects from `nolane.evaluation.parameters`.
- Produces: historical imports with exact object identity and no duplicate executable authority.

- [ ] **Step 1: Replace historical implementation with explicit imports**

```python
from nolane.evaluation.parameters import (
    ParameterFootprintReport,
    ScalingDecision,
    ScalingProposal,
    ScalingDecisionReceipt,
    ParameterScalingAuthority,
)

__all__ = (
    "ParameterFootprintReport",
    "ScalingDecision",
    "ScalingProposal",
    "ScalingDecisionReceipt",
    "ParameterScalingAuthority",
)
```

- [ ] **Step 2: Re-run exact identity and behavior contracts**

The historical identity test must pass without importing any historical executable implementation back into canonical code.

### Task 4: Cut over Refoundation authority and acceptance oracles

**Files:**
- Modify: `cogcoder/refoundation/component_versions.py`
- Modify: `cogcoder/refoundation/facades.py`
- Modify: `cogcoder/refoundation/implementation_status.py`
- Modify: `tests/test_refoundation_component_versions.py`
- Modify: `tests/test_refoundation_implementation_status.py`

**Interfaces:**
- Produces: `evaluation.parameters` revision 1, `CANONICAL_NATIVE` status, canonical module `nolane.evaluation.parameters`, canonical write authority, and no active compatibility facade.

- [ ] **Step 1: Advance the local component revision**

Add `"evaluation.parameters": 1` to `_COMPONENT_REVISIONS.update(...)` and to `ACCEPTED_COMPONENT_REVISIONS`; add focused version/next-version assertions if the acceptance file follows the existing explicit pattern.

- [ ] **Step 2: Retire only the parameter facade**

Remove only `FacadeBinding("evaluation.parameters", ...)` from `build_active_facade_bindings()`.

- [ ] **Step 3: Grant canonical-native implementation authority**

Add `evaluation.parameters` to `_NATIVE` with canonical module, historical source provenance, and a note describing native parameter-footprint/scaling-decision authority over canonical evidence/regime/identity/digest dependencies.

- [ ] **Step 4: Update the accepted-native oracle**

Add `evaluation.parameters` to `ACCEPTED_CANONICAL_NATIVE_COMPONENTS` and to the explicit canonical-write-authority acceptance set where applicable; do not mark neighboring evaluation components native.

### Task 5: Refresh current projections and preserve predecessor receipts

**Files:**
- Modify: `CURRENT/NATIVE_DEBT.json`
- Modify: `CURRENT/NATIVE_DEBT.md`
- Modify: `CURRENT/STATUS.md`
- Modify if required: `tests/test_refoundation_wave5ag_native_evaluation_evidence.py`

**Interfaces:**
- Produces: deterministic 15-record native-debt projection and a current Wave 5AH receipt.

- [ ] **Step 1: Materialize native debt**

Remove only `evaluation.parameters`; change compatibility-facade count from 10 to 9; leave five historical-only records and one frozen asset unchanged. The total must be 15.

- [ ] **Step 2: Add the Wave 5AH status receipt**

Record that parameter footprint, scaling proposal/decision, validation and state authority now live in `nolane.evaluation.parameters`, with the historical module as an exact bridge and native debt moving `16 -> 15`.

- [ ] **Step 3: Make the Wave 5AG debt assertion monotonic if it blocks downstream extraction**

Preserve the Wave 5AG historical fact that it retired `evaluation.evidence` and left no more than 16 records; do not let its test freeze all later waves at exactly 16.

### Task 6: Exact-head verification and PR receipt

**Files:**
- Modify only if fresh verification exposes a real defect or stale deterministic projection.
- Update PR body after final GREEN.

**Interfaces:**
- Produces: review-ready Wave 5AH PR with fresh exact-head verification evidence.

- [ ] **Step 1: Run/inspect fresh `Nolane-AI Refoundation Epoch 0` CI on the final head**

Both Python 3.11 and Python 3.13 must pass compile, 67 AI dossier freshness, repository-audit freshness, all `tests/test_refoundation_*.py`, evidence-bundle generation, organization/campaign/execution regressions, and frozen Neural R2.3 contracts.

- [ ] **Step 2: If CI fails, debug root cause rather than weakening contracts**

Use `superpowers:systematic-debugging`, inspect failing job logs, make the smallest root-cause correction, create a new head, and restart exact-head verification. Never reuse a green result from an older head.

- [ ] **Step 3: Update the PR receipt and mark ready**

Record RED commit/run, native cutover details, final exact SHA/run, pass counts, audit count 15, and deterministic projection evidence. Mark the PR ready for review only after the exact final head is GREEN; do not auto-merge unless explicitly required by repository policy.