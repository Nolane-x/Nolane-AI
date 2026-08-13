# Nolane AI — R2.4 Long-Horizon Replanning

Nolane AI is an experimental compact cognitive system built around a small neural core plus explicit memory, retrieval, epistemic verification, reusable skills, active experimentation and public-feedback replanning. The project deliberately separates **neural capability** from **hybrid runtime capability**.

## Current accepted system

The neural stack remains **78,779,253 effective parameters**:

- R1.9 FrontierRollout parent: **78,214,173**
- R2.0e EvidenceEffect executive: **+565,080**
- R2.0i Active Causal Discovery: **+0 neural parameters**
- R2.1a Cognition-Time Retrieval Fabric: **+0**
- R2.2 Epistemic Workspace: **+0**
- R2.3 Continual Skill Synthesis: **+0**
- R2.4 Long-Horizon Replanning: **+0**

R2.4 keeps the same single neural weight. It refreshes a public goal/dependency view after each transition instead of executing one initial snapshot plan unchanged.

## One deployment weight

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

The internal readiness rubric moves only modestly, from 17.0 to **18.2/100**. R2.4 improves evidence for long-range replanning, but broad reasoning, language/coding/math competence, multimodality and independent frontier-benchmark evidence remain weak.

## Scientific boundary

KFIGG-24 is synthetic and exposes goals, dependencies, actions and feedback. Its high score does not establish unrestricted real-world operation, human-level strategic judgment, AGI, or superiority to >100B/frontier models. Those claims require independent external benchmarks and matched-budget reference-model evaluations.

## GitHub binary boundary

GitHub `main` contains source, locks, results, manifests and CI. The current conversational GitHub connector still does not expose a practical local-binary/LFS/release-asset stream for the ~59.8MB `.pt`; therefore the repository records the exact weight SHA instead of pretending its bytes are stored in GitHub. Complete milestone artifacts are persisted to ChatGPT Library.

## License

Research code currently follows licenses embedded in imported/derived components. A repository-wide license should only be declared after those component licenses are audited.
