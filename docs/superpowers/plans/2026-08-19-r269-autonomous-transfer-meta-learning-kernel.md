# R2.69 Autonomous Transfer & Meta-Learning Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-trainable-parameter external cognitive kernel that compiles verifier-backed R2.68 experience into identity-free reusable priors, transfers them to unseen structurally related tasks with a shared transfer/scratch evidence ledger, bounds negative-transfer regret, and records scoped meta-credit/capability gaps.

**Architecture:** R2.69 is layered above accepted R2.68. `r269_causal_basis_adapter.py` is the only component allowed to interpret R2.68 receipts; it emits canonical `PortableExperience` objects. `r269_meta_learning_kernel.py` owns target-side matching, candidate generation, dual-use active probing, shared evidence, scratch continuation, quarantine, credit and gap receipts. The benchmark measures sequential heldout transfer against matched cold scratch and ablations; release workflows bind all claims to exact Git objects and protected R2.68 lineage.

**Tech Stack:** Python 3.11/3.13, existing `cogcoder.r256_operator_dsl`, accepted `cogcoder.r268_adaptive_causal_basis`, pytest, GitHub Actions, JSON evidence artifacts.

**Spec:** `docs/superpowers/specs/2026-08-19-r269-autonomous-transfer-meta-learning-kernel-design.md`

## Global Constraints

- R2.69 adds exactly `0` trainable neural parameters.
- Accepted parent is R2.68 merge `fda7f502185266fedb00886d5786c6d28cc0e0eb`; R2.68 protected tests must remain green.
- No target task ID, family ID, benchmark seed, source raw target values, target expected outputs or answer-derived digest may participate in prior retrieval, candidate generation or candidate ordering.
- Every physical target oracle attempt is represented exactly once in one shared immutable observation ledger.
- Transfer-selected diagnostic queries must satisfy a frozen scratch-information floor computed before the target output is observed.
- Terminal evidence is acceptance-only and may not resolve diagnostic ambiguity.
- Negative transfer must fail closed; scratch continuation reuses the same purchased observations and never restarts evidence accounting.
- Meta-credit requires an accepted target receipt plus a matched source-prior ablation showing the measured advantage disappears.
- Capability gaps are keyed by verifier-backed failure signatures/public structure, never target identity.
- CI success is implementation evidence, not an AGI or W5-convergence claim.

---

### Task 1: Portable verified experience boundary

**Files:**
- Create: `cogcoder/r269_causal_basis_adapter.py`
- Test: `tests/test_r269_portable_experience.py`

**Interfaces:**
- Produces `VerifiedExperienceEnvelope`, `PortableExperience`, `compile_r268_experience(...)`, `portable_experience_from_data(...)`.
- `compile_r268_experience(receipt: AdaptiveCausalBasisReceipt, *, source_authority_digest: str, accepted_parent_sha: str) -> PortableExperience`.
- Portable roles are canonical `__r0..__rN`; the object contains no source identifiers or raw labels.

- [ ] **Step 1: Write failing authority tests**

Tests must instantiate a minimal verifier-backed accepted R2.68 receipt fixture and assert: unpassed/non-minimal/incomplete-proof receipts are rejected; direct `PortableExperience` construction rejects forged digest/parameter count/noncanonical roles; serialization contains no source field names, intervention IDs, task/family IDs or raw source target values; round-trip preserves digest and canonical expression.

- [ ] **Step 2: Run RED**

Run: `PYTHONPATH=. pytest -q tests/test_r269_portable_experience.py`
Expected: collection/import failure because `cogcoder.r269_causal_basis_adapter` does not exist.

- [ ] **Step 3: Implement the adapter**

Use existing `Expr` tree types. Recursively collect used source fields, sort them deterministically, rewrite them to canonical roles, bind expression digest + authority digest + accepted-parent SHA + role count + claim scope into a SHA-256 portable digest, and validate every field again in `__post_init__`. The adapter must never serialize source field names.

- [ ] **Step 4: Run GREEN and parent smoke**

Run: `PYTHONPATH=. pytest -q tests/test_r269_portable_experience.py tests/test_r268_*.py`
Expected: all pass.

- [ ] **Step 5: Commit**

Commit message: `feat(r269): add verifier-backed portable experience boundary`.

### Task 2: Structural matcher and shared observation ledger

**Files:**
- Create: `cogcoder/r269_meta_learning_kernel.py`
- Test: `tests/test_r269_shared_evidence.py`
- Test: `tests/test_r269_matching_authority.py`

**Interfaces:**
- Produces `PublicTaskSignature`, `MatchedPrior`, `SharedObservation`, `SharedObservationLedger`, `match_portable_experiences(...)`.
- `PublicTaskSignature` exposes `role_names`, `numeric_domain`, `allowed_binary_ops`, `query_space_digest`, `budget_contract`; `task_name` is not accepted by the constructor.
- `SharedObservationLedger.observe(...)` owns every oracle call and returns one content-addressed row; consumers receive the row, not permission to call the oracle again.

- [ ] **Step 1: Write failing matching/ledger tests**

Assert matcher output is invariant to prior insertion order and arbitrary external target labels; incompatible role cardinality is rejected; duplicate semantic query attempts return the existing observation without a second oracle call; oracle exception/non-finite output is recorded once and fails closed; diagnostic and terminal semantic keys cannot overlap.

- [ ] **Step 2: Run RED**

Run: `PYTHONPATH=. pytest -q tests/test_r269_shared_evidence.py tests/test_r269_matching_authority.py`
Expected: import failures for missing kernel.

- [ ] **Step 3: Implement matcher/ledger**

Canonicalize numeric contexts, isolate oracle mutation exactly as the existing transfer research does, content-address queries by ordered target role values, and calculate matcher compatibility only from role count/operator/domain/query-space public metadata plus portable applicability constraints.

- [ ] **Step 4: Run GREEN**

Run the two R2.69 files plus `tests/test_r268_*.py`.

- [ ] **Step 5: Commit**

Commit message: `feat(r269): add structural retrieval and shared target evidence`.

### Task 3: Transfer, dual-use probing, scratch continuation and quarantine

**Files:**
- Modify: `cogcoder/r269_meta_learning_kernel.py`
- Test: `tests/test_r269_transfer_governor.py`
- Test: `tests/test_r269_negative_transfer.py`

**Interfaces:**
- Produces `MetaLearningConfig`, `MetaLearningReceipt`, `PriorState`, `PriorRegistry`, `run_meta_learning_episode(...)`, `run_cold_scratch(...)`.
- `run_meta_learning_episode(priors, signature, diagnostic_contexts, terminal_contexts, oracle, config, registry=None) -> MetaLearningReceipt`.
- Transfer and scratch maintain separate hypothesis sets but consume identical `SharedObservation` rows.

- [ ] **Step 1: Write failing behavior tests**

Cover: related prior reaches a unique hypothesis with fewer fresh observations than cold scratch; transfer-guided query is issued only when its pre-observation scratch partition count meets the configured floor; wrong prior elimination switches to scratch without replaying existing oracle calls; terminal evidence never converts a diagnostically ambiguous state into success; quarantine prevents the same prior from influencing later matching; a target outside all priors starts directly in scratch mode; false terminal accepts remain zero.

- [ ] **Step 2: Run RED**

Run the two new test files; expect missing functions/types.

- [ ] **Step 3: Implement candidate/search engine**

Generate prior candidates from canonical prior expression using target-role permutations plus one bounded binary-operator substitution. Generate matched scratch hypotheses over the same target roles/operator vocabulary. Deduplicate only proof-backed structural aliases. For each unused diagnostic context compute transfer partition score and scratch partition score before oracle observation; prefer the best transfer query only if the scratch floor passes, otherwise use the scratch-optimal query. Update both live sets from the single shared observation. If transfer dies or exceeds budget, continue scratch from the existing live scratch set/ledger. Require a singleton before entering terminal verification.

- [ ] **Step 4: Implement bounded-regret/quarantine receipts**

Receipt fields include mode, selected prior ID, physical diagnostic calls, physical terminal calls, transfer/scratch candidates considered, reused observation count, avoided duplicate calls, transfer contradiction count, quarantine action, false accepts and exact reason. Registry credit/quarantine state is content-addressed and cannot be bypassed by constructing a new object with the same prior digest.

- [ ] **Step 5: Run GREEN + R2.68 protected tests**

Run all `tests/test_r269_*.py` plus `tests/test_r268_*.py`.

- [ ] **Step 6: Commit**

Commit message: `feat(r269): add bounded-regret transfer and scratch continuation`.

### Task 4: Meta-credit, ablation and capability-gap ledger

**Files:**
- Modify: `cogcoder/r269_meta_learning_kernel.py`
- Test: `tests/test_r269_meta_credit.py`

**Interfaces:**
- Produces `MetaCreditRecord`, `CapabilityGapRecord`, `MetaCreditLedger`, `CapabilityGapLedger`, `adjudicate_prior_credit(...)`, `record_capability_gap(...)`.

- [ ] **Step 1: Write failing governance tests**

Assert credit is denied without terminal acceptance; denied when prior ablation retains the same cost/solve advantage; allowed only when the prior materially changes matched budget outcome; repeated negative regret yields quarantine; gap records reject task/family/answer-derived identity fields and require verifier receipt digests + typed gap class + closure evidence requirement.

- [ ] **Step 2: Run RED**

Run `PYTHONPATH=. pytest -q tests/test_r269_meta_credit.py`.

- [ ] **Step 3: Implement credit/gap governance**

Credit scope is keyed by public signature class + portable digest. Gap clustering key is a hash over gap type, public signature class and sorted failure signatures. Records are immutable and expose explicit rollback/quarantine state.

- [ ] **Step 4: Run GREEN**

Run all R2.69 and R2.68 tests.

- [ ] **Step 5: Commit**

Commit message: `feat(r269): add scoped meta-credit and capability-gap governance`.

### Task 5: Sequential authored benchmark and matched controls

**Files:**
- Create: `benchmarks/kfigg/r269_meta_learning.py`
- Test: `tests/test_r269_benchmark.py`

**Interfaces:**
- Produces `run_benchmark() -> dict[str, object]` with exact counts and per-case receipts.

- [ ] **Step 1: Write failing benchmark contract**

Assert benchmark result reports: related target totals/solves, negative totals/false accepts, transfer/cold-scratch/roomy-scratch physical oracle counts, proof-distinct candidate work, source-prior ablation, shuffled-prior ablation, continued-scratch correctness, regret distribution, deterministic replay digest and `trainable_parameter_count == 0`.

- [ ] **Step 2: Run RED**

Run benchmark test; expect missing benchmark module.

- [ ] **Step 3: Implement source + heldout sequence**

Use canonical numeric expression families over 2/3/4 roles. Build at least 18 related targets with role permutations/surface shifts and at least 12 negative targets spanning wrong cardinality/topology, early misleading agreement, terminal contradiction and invalid oracle behavior. Pair each target with cold scratch and appropriate ablation controls under identical physical query budgets.

- [ ] **Step 4: Encode claim gate**

Promotion-level result requires zero false accepts, deterministic replay, exact ledgers, transfer advantage over cold scratch in both fresh target calls and proof-distinct search, ablation loss of advantage, bounded negative-transfer regret, and roomy scratch expressibility. If oracle reduction fails while search reduction passes, set `passed=False` for the strong R2.69 claim but retain the narrower measured fields.

- [ ] **Step 5: Run GREEN twice**

Run `PYTHONHASHSEED=1 ...` and `PYTHONHASHSEED=777 ...`; serialized semantic result digest must match.

- [ ] **Step 6: Commit**

Commit message: `test(r269): add sequential meta-learning benchmark`.

### Task 6: Hosted RED→GREEN, evidence, docs and release authority

**Files:**
- Create: `.github/workflows/r269-red-green.yml`
- Create: `.github/workflows/r269-canonical.yml`
- Create: `.github/workflows/r269-release-bundle.yml`
- Create: `.github/workflows/r269-post-merge-release-bundle.yml`
- Create after source freeze: `archive/root-history/historical_r_series/R2_69_PHASE_A_RESULT.json`
- Create after source freeze: `archive/root-history/historical_r_series/R2_69_PRE_HOSTED_LOCK.json`
- Create: `R2_69_DELIVERY.md`
- Modify: `archive/root-history/legacy_current_status/CURRENT_STATUS.md`

**Interfaces:**
- RED workflow runs R2.68 protected safety first, then R2.69 contract tests on Python 3.11/3.13.
- Canonical workflow verifies exact lock blobs, recomputes Phase-A JSON byte/canonical-hash equivalence, runs R2.69 + protected lineage and publishes `r269/full-gate` only after all jobs succeed.
- Release workflow produces `Nolane-AI-R2.69-COMPLETE.zip`; post-merge repeats exact-main evidence, Python 3.13 replay, protected lineage and ZIP integrity before `r269/post-merge-bundle=success`.

- [ ] **Step 1: Materialize initial hosted RED before production implementation**

The first workflow commit contains only tests + workflow and must fail specifically because R2.69 production symbols/modules are absent. Record run ID in the later lock/evidence record.

- [ ] **Step 2: Run hosted GREEN after implementation**

Require Python 3.11 and 3.13 focused R2.69 GREEN and accepted R2.68 protected safety GREEN.

- [ ] **Step 3: Freeze source and evidence**

Lock exact Git blob SHAs for spec, plan, modules, benchmark, tests and workflows. Recompute authored evidence only after freeze. Record exact parent ancestry, red/green run IDs, trainable parameter count, claim boundary, and Nolane World bounded adjudication without forcing W5 convergence.

- [ ] **Step 4: Run canonical + release bundle**

Require exact evidence recomputation, protected parent lineage, deterministic replay and COMPLETE ZIP integrity.

- [ ] **Step 5: Merge exact head and run exact-main post-merge gate**

Merge with expected head SHA. Final acceptance requires post-merge run success on the merge commit; otherwise release remains invalid.

- [ ] **Step 6: Persist final artifact**

Download the verified post-merge COMPLETE ZIP, independently verify its internal SHA/integrity, and persist a copy to Library.

## Plan self-review

- Spec coverage: every architecture component is assigned to Tasks 1–6; external transfer is deliberately deferred from authored implementation until Task 6 evidence work because the external family must remain independently sourced rather than co-designed with core code.
- Placeholder scan: no TBD/TODO/"implement later" placeholders are used as executable requirements.
- Type consistency: `PortableExperience` flows from Task 1 into matcher/transfer/credit; `SharedObservationLedger` is the sole target oracle owner; `MetaLearningReceipt` is the sole target-side authority input for credit/benchmark evidence.
- Scope: R2.69 Phase A implements one `causal_basis_v1` adapter and generic governance interfaces; effectful filesystem/network experiments and neural updates remain outside this milestone.