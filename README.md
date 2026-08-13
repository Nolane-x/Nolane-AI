# Nolane AI — R2.3 Continual Skill Synthesis

Nolane AI is an experimental compact cognitive system built around a small neural core plus explicit memory, retrieval, epistemic verification, active experimentation and external reusable skills. The project deliberately separates **neural capability** from **hybrid runtime capability**.

## Current accepted system

The neural stack remains **78,779,253 effective parameters**:

- R1.9 FrontierRollout parent: **78,214,173**
- R2.0e EvidenceEffect executive: **+565,080**
- R2.0i Active Causal Discovery: **+0 neural parameters**
- R2.1a Cognition-Time Retrieval Fabric: **+0**
- R2.2 Epistemic Workspace: **+0**
- R2.3 Continual Skill Synthesis: **+0**

R2.3 keeps the same single neural weight. It can infer a bounded reusable skill from public input/output demonstrations, persist it outside weights, apply it to unseen inputs, retain unrelated skills after intervening learning, adopt a newer demonstrated version, and compose previously acquired skills.

## One deployment weight

`Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`

- size: **59,773,663 bytes**
- SHA-256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`
- neural parameters: **78,779,253**

R2.1, R2.2 and R2.3 are zero-neural-parameter runtime upgrades, so a new neural checkpoint is intentionally not created.

## R2.3 locked continual-transfer evidence

The final KFIGG-23 protocol was selected using TRAIN only: three demonstrations per skill, seen probability 0.35, composition-seen probability 0.25, maximum induction depth 3 and candidate budget 100000. The persistent replay baseline receives the same demonstrations and persistent storage permission.

| Split | Persistent replay | R2.3 | Gain |
|---|---:|---:|---:|
| TRAIN 6000..6199 | 33.625% | **94.625%** | **+61.0 pp** |
| DEV 7000..7199 | 33.25% | **94.25%** | **+61.0 pp** |
| Final held-out 8000..8199 | 33.75% | **93.125%** | **+59.375 pp** |

Final held-out sub-capabilities: induction **94.0%**, retention **96.5%**, revision **92.5%**, composition **89.5%**, integrity failures **0**, synthesis failures **0**.

Successful GitHub Actions runs:

- DEV admission: `31705841354`
- final held-out: `31706020197`
- exact release integrity: `31706520042`

The held-out range 8000..8199 is consumed and the accepted candidate is frozen for this claim.

## Previous accepted evidence retained

- R2.2 KFIGG-22 final held-out: R2.1 baseline **51%**, R2.2 **100%**, +49 pp, zero provenance/version errors.
- R2.1a KFIGG-21 final held-out: retrieve-once **67%**, interleaved retrieval **100%**, +33 pp under the same four-chunk budget.
- R2.0i FIGG-18 final held-out: frozen neural baseline **36.25%**, hybrid active-causal runtime **60.0%**, +23.75 pp; causal-prerequisite family **5% -> 100%**.

## Verification

- `research/R2_3_CURRENT_BEST.json` — current accepted state and exact results.
- `research/R2_3_STAGE3_FREEZE.md` — freeze marker committed before final held-out evaluation.
- `research/R2_3_REALITY_REPORT.md` — scientific claim boundary.
- `research/AGI_READINESS_R2_3.md` — engineering readiness rubric.
- `scripts/verify_r23_release.py` — exact source/held-out verifier.
- `.github/workflows/r23-integrity.yml` — GitHub integrity gate.

The current engineering AGI-readiness rubric is **17/100**, not an AGI probability. Only the continual-learning dimension increased after R2.3; broad reasoning, language/coding/math competence, long-horizon autonomy, multimodality and independent frontier-benchmark evidence remain weak.

## Scientific boundary

KFIGG-23 is synthetic and deliberately restricted. R2.3 does **not** establish unrestricted lifelong learning, broad natural-language learning, general coding or mathematics competence, AGI, or superiority to >100B/frontier models. Those claims require independent external benchmarks and matched-budget reference-model evaluations.

## GitHub binary boundary

GitHub `main` contains source, tests, locks, results, manifests and CI. The current conversational GitHub connector still does not expose a practical local-binary/LFS/release-asset stream for the ~59.8MB `.pt`; therefore the repository records the exact weight SHA instead of pretending its bytes are stored in GitHub. Complete milestone artifacts are persisted to ChatGPT Library.

## License

Research code currently follows licenses embedded in imported/derived components. A repository-wide license should only be declared after those component licenses are audited.
