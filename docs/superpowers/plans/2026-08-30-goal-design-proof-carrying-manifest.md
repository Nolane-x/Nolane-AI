# Goal/Design Proof-Carrying Decision Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind every admitted Goal/Design decision identity to the complete semantic input state that justified it, while preserving deterministic content addressing and backward-safe authority persistence.

**Architecture:** Extend the canonical digest boundary in `nolane/external_core/goal_design.py` rather than adding a second manifest store. Domain dataclasses remain immutable; their complete canonical state is hashed into named manifest digests, the evaluation digest binds GoalSpec + scenario set + complete option set + computed evaluation, and the receipt ID binds those manifest digests plus the exact five-plane snapshot. Existing runtime/ledger layers consume the enriched immutable `DecisionReceipt` without becoming owners of decision semantics.

**Tech Stack:** Python 3.11/3.12, frozen dataclasses, canonical JSON/SHA-256 through `stable_digest`, pytest, GitHub Actions.

**Spec:** `docs/GOAL_DESIGN_COHERENCE_PLANE.md`

## Global Constraints

- Requirements, Planning, Architecture, Integration and Context remain separate specialist authorities.
- Truth / Knowledge and Software Engineering remain separate external-core authorities; Goal/Design consumes immutable identity/evidence and does not take ownership of either surface.
- Exact five-plane snapshot binding remains fail-closed.
- Decision receipt identity must be deterministic for identical semantic inputs.
- Semantic changes to goal, scenarios, options, proof state, uncertainty state or traceability must change the appropriate manifest digest and decision receipt identity.
- Receipt audit lineage must retain evidence from every option actually evaluated, not only the selected option.
- No new runtime dependency is introduced into the Goal/Design production authority.
- Existing Goal/Design tests must remain green on Python 3.11 and 3.12.

---

### Task 1: Canonical decision input manifest

**Files:**
- Modify: `nolane/external_core/goal_design.py`
- Test: `tests/test_goal_design_decision_manifest.py`

**Interfaces:**
- Consumes: `stable_digest(value) -> str`, `GoalSpec`, `DesignScenario`, `DesignOption`, `ProofObligation`, `UncertaintyItem`, `TraceabilityState`.
- Produces: enriched `DecisionReceipt` fields `goal_digest`, `scenario_set_digest`, `option_set_digest`, `proof_state_digest`, `uncertainty_state_digest`, `traceability_digest`, `input_manifest_digest`.

- [x] **Step 1: Write the failing tests**

The committed tests require semantic receipt identity changes for goal assumptions, option dependencies, proof status/waiver state and uncertainty resolution state, while identical complete inputs remain deterministic.

- [x] **Step 2: Run tests to verify RED**

Run: `python -m pytest -q tests/test_goal_design*.py`

Observed RED: seven manifest tests failed while 32 existing Goal/Design tests remained green.

- [x] **Step 3: Implement canonical manifest digests**

The implementation hashes complete canonical immutable state for GoalSpec, scenarios, options, proof obligations, uncertainties and traceability. `traceability=None` is a real semantic state and is hashed as such. The manifest additionally binds the selected option and exact snapshot/version vector so authority closure cannot be replayed against different five-plane state.

- [x] **Step 4: Bind evaluation and receipt identities**

`DesignEvaluation.digest` includes the canonical goal, scenario set and option set in addition to computed evaluation rows. `DecisionReceipt.receipt_id` includes `input_manifest_digest`, the exact snapshot/version vector, selected option and evaluation digest.

- [x] **Step 5: Run focused tests GREEN**

Observed GREEN as part of the complete Goal/Design suite.

### Task 2: Persistence and causal ledger compatibility

**Files:**
- `nolane/external_core/goal_design_runtime.py`
- `nolane/external_core/goal_design_ledger.py`
- `tests/test_goal_design_authority_persistence.py`
- `tests/test_goal_design_runtime.py`
- `tests/test_goal_design_ledger.py`

- [x] Serialization/deserialization round-trips every proof-carrying digest with backward-compatible defaults for legacy state.
- [x] Typed DECISION ledger events bind `input_manifest_digest` directly.
- [x] Decision lifecycle, dependencies, invalidation and supersession survive restart.

### Task 3: Complete evaluated-option evidence lineage

**Files:**
- Modify: `nolane/external_core/goal_design.py`
- Test: `tests/test_goal_design_decision_manifest.py`

- [x] **RED proof:** exact commit `02505bb6b88bef2f1e335baf36e0586d77e39595` produced one intended failure on Python 3.12 while 45 tests passed. `DecisionReceipt.evidence_refs` contained `ev:selected` but omitted `ev:alternate`, proving the receipt materialized evidence only from the selected option even though the alternative participated in evaluation/Pareto authority.
- [x] **Production fix:** receipt evidence collection now unions evidence from every `canonical_options` entry before scenarios/proofs/uncertainties are added. No scoring, manifest, lifecycle or specialist-authority semantics changed.
- [x] **GREEN proof:** exact commit `ab3c6c6fa9505b245549bffbc5b3e638830f8582`, workflow run `33313174733`, passed 46/46 on Python 3.11 and 46/46 on Python 3.12.

### Task 4: Cross-authority composition gates

**A — Truth / Knowledge**

- [x] Pre-A RED proof `d7d27b01eff2952913648f5055b12b894acdee95` failed exactly at import of the then-absent `nolane.external_core.evidence_truth` authority.
- [x] TruthEvidence `content_digest` is treated as immutable evidence identity and flows into D receipt identity without D becoming the Truth authority.
- [x] Truth content identity changes alter Goal/Design goal/receipt identity.

**F — Software Engineering**

- [x] F treats a D `input_manifest_digest` as an opaque immutable `subject_digest`; F does not gain Goal/Design decision authority.
- [x] F evidence identity changes when the D manifest changes.
- [x] `EngineeringEvidenceLedger.is_valid()` accepts the exact D manifest binding and rejects a tampered subject digest.
- [x] Pre-A8 merged-baseline head `0180ae7c486d1fb6f23654d8a25b6a606a2f8cad`, workflow run `33313296451`, passed 47/47 on Python 3.11 and 47/47 on Python 3.12.

**Refoundation A8 — dependency-scoped Truth binding**

- [x] Current A8 main `64d1ed5ad816e731068f0612db90c5b32288a465` is integrated as the specialist baseline through merge commit `5741b84332edcfed0c540e72d6d5ab82528381de`.
- [x] The A8 tree is preserved byte-for-byte outside the 15 D-owned paths by constructing the union from A8 tree `132a8203b895eb03071440c0ad80b18cbbddffef` and overlaying only verified D blobs.
- [x] The A8 interop contract uses `EvidenceLedger.scoped_digest()` as an immutable dependency-scope identity and requires active→revoked scoped Truth state to change D authority identity, while keeping Truth state ownership in A8.

### Task 5: Final verification and PR closure

- [ ] Exact A8+D+F final candidate passes every `tests/test_goal_design*.py` test on Python 3.11 and Python 3.12.
- [ ] Refresh `main`; if it materially changed after A8 integration, integrate and re-run the merged-baseline gate.
- [ ] `main...feat/goal-design-coherence-plane-gpt56sol` is `behind_by=0`, mergeable, and its changed-file set contains only Goal/Design implementation, tests, documentation, compatibility export and dedicated workflow.
- [ ] Reopen PR #239 with final RED→GREEN and cross-authority evidence.
- [ ] Merge PR #239 with exact-head protection and verify the returned merge SHA is the new `main` SHA.
