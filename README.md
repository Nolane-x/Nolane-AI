# Nolane AI — R2.4 Long-Horizon Replanning

Nolane AI is an experimental compact cognitive system built around a small neural core plus explicit memory, retrieval, epistemic verification, reusable skills, active experimentation and public-feedback replanning. The project deliberately separates **neural capability** from **hybrid runtime capability**.

## Active coding research track — not externally promoted

The repository now contains an experimental coding-generalization track beyond the currently accepted R2.4 system:

- **R2.7 CodeWorld Phase A:** adds a 622,147-parameter coding-loop controller, producing **79,401,400** effective neural parameters. Its internal language×task-pair curriculum is a workflow-policy gate only, not evidence of general repository coding performance.
- **R2.8 Repository World Model Phase A:** adds **0 neural parameters**. It represents repository dependency/test topology, maintains competing fault hypotheses, and selects legal coding actions using expected information gain plus graph-derived edit risk. Its locked four-case architecture gate and full node/hypothesis renaming invariance pass internally.
- **R2.9 Verifier-Guided Patch Search Phase A:** adds **0 neural parameters**. It performs canonicalized, hard-budget patch search with executable verification, R2.8 blast-radius risk, failure-memory refinement, and candidate-id-invariant traces. Its locked executable Python/JavaScript micro-repository gate resolves **4/4** cases with **0 false terminal accepts**, **0 duplicate evaluator calls**, and at most **2** evaluator calls per case.

External coding claims remain disabled. R2.7/R2.8/R2.9 have not yet established arbitrary patch generation or fresh-repository issue-resolution performance; R2.9 searches/refines supplied candidates but is not yet a general source-code decoder. Those claims require a source-aware proposer plus executable external evaluation on fresh and broad repository tasks.

## Current accepted system

The broadly accepted pre-coding-research system remains R2.4. Its neural stack is **78,779,253 effective parameters**:

- R1.9 FrontierRollout parent: **78,214,173**
- R2.0e EvidenceEffect executive: **+565,080**
- R2.0i Active Causal Discovery: **+0 neural parameters**
- R2.1a Cognition-Time Retrieval Fabric: **+0**
- R2.2 Epistemic Workspace: **+0**
- R2.3 Continual Skill Synthesis: **+0**
- R2.4 Long-Horizon Replanning: **+0**

R2.4 keeps the same single neural weight. It refreshes a public goal/dependency view after each transition instead of executing one initial snapshot plan unchanged.

## One accepted R2.4 deployment weight

`Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`

- size: **59,773,663 bytes**
- SHA-256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`
- neural parameters: **78,779,253**

R2.1 through R2.4 are zero-neural-parameter runtime upgrades, so a new neural checkpoint is intentionally not created.

## R2.4 locked evidence — KFIGG-24

The final protocol uses 16–24 core goals and a fixed 26-step budget. Both modes receive the same public goals, dependencies, actions and feedback.

| Split | Snapshot sequence | Observation-refresh sequence | Difference |
|---|---:|---:|---:|
| TRAIN 10000..10199 | 33.0% | **95.0%** | **+62.0 pp** |
| Stage 2 11000..11199 | 33.5% | **93.5%** | **+60.0 pp** |
| Stage 3 12000..12199 | 33.5% | **94.5%** | **+61.0 pp** |

Stage-3 requirement-change completion: **91.73%**. Transient-event completion: **88.89%**. Candidate blocked attempts: **0**. Mean steps on completed candidate episodes: **21.52**.

Successful GitHub Actions runs:

- Stage 2 admission: `31709604495`
- Stage 3 check: `31709736674`
- exact integrity: `31710180356`

## Previous accepted evidence retained

- R2.3 KFIGG-23 final held-out: persistent replay **33.75%**, R2.3 **93.125%**, +59.375 pp.
- R2.2 KFIGG-22 final held-out: R2.1 **51%**, R2.2 **100%**, +49 pp.
- R2.1a KFIGG-21 final held-out: retrieve-once **67%**, interleaved retrieval **100%**, +33 pp.
- R2.0i FIGG-18 final held-out: frozen neural baseline **36.25%**, hybrid runtime **60.0%**, +23.75 pp.

## Verification

- `research/R2_4_STATUS.json` — accepted R2.4 state and exact metrics.
- `research/R2_4_PRE_DEV_LOCK.md` — protocol/source lock before stage 2.
- `research/R2_4_STAGE3_FREEZE.md` — source freeze before stage 3.
- `.github/workflows/r24-integrity.yml` — exact Git blob and aggregate gate.
- `research/R2_8_PRE_DEV_LOCK.json` — R2.8 zero-parameter architecture gate.
- `research/R2_8_PHASE_A_RESULT.json` — R2.8 internal routing result and claim boundary.
- `research/R2_9_PRE_DEV_LOCK.json` — preregistered R2.9 executable patch-search thresholds.
- `research/R2_9_PHASE_A_RESULT.json` — R2.9 measured result and claim boundary.

The R2.4 internal readiness rubric was **18.2/100**. The newer coding research track does not automatically increase that broad AGI/readiness score; broad reasoning, language/coding/math competence, multimodality and independent frontier-benchmark evidence remain insufficient.

## Scientific boundary

KFIGG evidence is synthetic; R2.8 Phase A is a small adversarial routing gate; and R2.9 Phase A is a small executable micro-repository patch-search gate. Neither establishes unrestricted real-world operation, human-level strategic judgment, AGI, or superiority to >100B/frontier models. Those claims require independent external benchmarks and matched-budget reference-model evaluations.

## GitHub binary boundary

GitHub `main` contains source, locks, results, manifests and CI. Large neural checkpoints are recorded by exact SHA and persisted with complete milestone artifacts outside normal Git source when required.

## License

Research code currently follows licenses embedded in imported/derived components. A repository-wide license should only be declared after those component licenses are audited.
