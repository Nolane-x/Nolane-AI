# R2.64 — Unified Adaptive Repository Search

## Status

**ACCEPTED_BOUNDED_CAPABILITY CANDIDATE — pending final release-bundle integrity gate and merge into `main`.**

R2.64 unifies two previously separated repository-search capabilities. Accepted R2.61 could expand after an active diagnostic oracle result fell outside a multi-candidate version space, but its first verified singleton was terminal. Accepted R2.63 could compose additional trusted edits from refinement counterexamples after a singleton survived, but it deliberately abstained when the initial diagnostic result was outside the supplied candidate space. R2.64 maintains one public evidence ledger across both phases: diagnostic out-of-space expansion can create a partial repair, then a separate refinement counterexample can justify another target-output-free trusted `PatchMacro` expansion before disjoint terminal verification.

Added trainable parameters: **0**.

## Runtime mechanism

`cogcoder/r264_unified_adaptive_repository_search.py` provides:

- content-canonicalized repository candidate identity independent of caller IDs;
- deterministic bounded `AdaptiveFrontierCandidate` generation from trusted R2.47/R2.61 `PatchMacro` semantics;
- complete-repository seen-state suppression to prevent content cycles;
- content-addressed parent/child mutation provenance and an inspectable accepted mutation chain;
- R2.60 minimax active diagnostic selection while multiple candidates survive;
- public diagnostic counterexamples that may trigger bounded expansion when the oracle label is outside the current partitions;
- public singleton refinement counterexamples that may trigger later bounded composition;
- hard selection/refinement/round/depth/generation/site budgets;
- unique/disjoint terminal verification that can reject an answer but cannot be recycled into learning;
- fail-closed receipts for missing authority, exhausted budgets, oracle errors, unexpressible targets and terminal verification failures.

`expand_adaptive_repository_frontier(...)` exposes no oracle, target or expected-output parameter. Oracle labels can filter only after target-independent candidate generation.

## Authored causal evidence

`R2_64_PHASE_A_RESULT.json` freezes six multi-file episodes with 4–8 files and relay depth 0–2. Every exact two-edit target is absent from both the initial repository-content space and the complete one-step trusted-macro frontier.

Observed results:

- accepted R2.63: **6/6 abstain** with `oracle_outside_initial_candidate_version_space` before expansion;
- R2.64: **6/6 exact**;
- diagnostic counterexamples: **6/6**;
- refinement counterexamples: **6/6**;
- exactly two expansion rounds and depth two: **6/6**;
- public diagnostic/refinement observations preserved: **6/6**;
- disjoint final verification: **31–32 cases per episode**;
- candidate-order invariance: PASS;
- caller-ID invariance: PASS;
- target-output-free generation: PASS;
- adversarial negative abstains: **10/10**;
- false terminal accepts: **0**;
- positive verification failures: **0**.

The negative suite covers expansion-round, composition-depth, missing-macro, selection, refinement, generation and oracle-error boundaries, an unexpressible target, and a terminal heldout contradiction that is not recycled into expansion.

## External callable-I/O transfer

`R2_64_EXTERNAL_TRANSFER.json` freezes a causal transfer against **NumPy 2.4.6 `numpy.square`**, exposed only as callable I/O.

The five-file wrapper begins with `Add` behavior on the positive and negative paths plus a connected decoy site. A second executable initial candidate changes the positive path to a different wrong behavior. At diagnostic input `5`, neither initial behavior equals NumPy square, so the accepted R2.63 baseline abstains at its initial version-space boundary after one oracle call.

R2.64 instead:

1. records the diagnostic square label as public evidence;
2. generates a bounded `Add → Mult` trusted-macro frontier without target-output access;
3. admits the positive-path partial repair;
4. receives a separate refinement counterexample at `-5`;
5. composes the second `Add → Mult` mutation;
6. passes **46/46** disjoint final verification inputs.

The exact target repository is evaluation-only, absent from both the initial and complete one-step spaces, and never supplied to either solver. R2.64 uses **48** oracle calls (1 diagnostic + 1 refinement + 46 final verification); the matched accepted R2.63 causal baseline uses **1**. Total external calls reported by the harness are **49**. Source implementation inspection is false, false terminal accepts are zero, and the accepted mutation chain contains exactly two distinct content-addressed mutations.

## TDD and hosted verification

`R2_64_TDD_RED.json` records hosted missing-module RED gates for the core, authored benchmark and external harness before each implementation layer existed.

The canonical proof run is GitHub Actions **32131078117** on branch head `9e49f9c5a70a189e29cd0f27944624ae1345b43e`, PR merge tree `777cb57cf8f6393fb90cfddbd6906ae0cee532c6`, based on accepted R2.63 main `1d1b05e0c1476327eaf3b2457aab16153a43c429`.

- canonical job `95692143439`: success;
- publish job `95695935177`: success;
- frozen six-blob source lock: PASS;
- exact Phase-A recomputation: PASS;
- exact NumPy 2.4.6 square transfer recomputation: PASS;
- R2.64 focused: **9/9 PASS**;
- Python 3.11: PASS;
- Python 3.13: PASS;
- protected accepted R2.63→R2.41 lineage: **234/234 PASS**;
- published gate dependency chain: success.

The parent count is taken from the canonical logs: R2.63 7, R2.62 6, R2.61 16, R2.60 7, R2.59 12, R2.58 11, R2.57 15, R2.56 16, R2.55 19, R2.54–R2.50 56 and R2.49–R2.41 69.

## Nolane World 0.8.0

World `world4_710989051aaa4ef3` has a valid audit at epoch 7 with digest `a39a2f8fdc11cb711cded3d1537912d4bffb17fc85680270bf6409a8bcc76cc3`. The stored runtime state contains one fresh hosted verifier and one survived independent challenger. The challenger explicitly preserves the unresolved boundaries around learned patch-language growth, deeper-than-two edit scaling, effectful experiments and blind real-repository transfer.

**W5 remains FAIL, score 0.0.** The convergence court is not overridden by model narrative; residency/epoch, unresolved-unknown, verification/challenger-depth, robust-world, representation-diversity, value-of-thought and quality-floor requirements remain unsatisfied.

## Readiness calibration

Internal engineering readiness: **49.4/100**, up **+0.3** from accepted R2.63's 49.1. This is an engineering heuristic, not an AGI probability. The movement is limited because R2.64 composes existing bounded mechanisms over a host-supplied representation, probe pools and trusted patch vocabulary; the external wrapper remains synthetic and the accepted chain depth is two.

## Release acceptance rule

R2.64 may be merged only if the final release-bundle workflow independently rechecks required files, the frozen Git blobs, exact Phase-A/external recomputation, hosted/World/readiness boundaries, focused regressions, complete repository ZIP creation and archive integrity. The bundle must then be regenerated and independently verified from the exact post-merge `main` commit before Library persistence.
