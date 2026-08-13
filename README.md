# Nolane AI — R2.2 Epistemic Workspace

Nolane AI is an experimental compact cognitive system built around a small neural core plus explicit memory, verification, active experimentation and external knowledge access. The project deliberately separates **neural capability** from **hybrid runtime capability**.

## Current accepted system

The neural stack remains **78,779,253 effective parameters**:

- R1.9 FrontierRollout parent: **78,214,173**
- R2.0e EvidenceEffect executive: **+565,080**
- R2.0i Active Causal Discovery: **+0 neural parameters**
- R2.1a Cognition-Time Retrieval Fabric: **+0**
- R2.2 Epistemic Workspace: **+0**

R2.2 keeps the same one neural weight and strengthens the runtime instead of storing all world knowledge in model weights. It can repeatedly retrieve during cognition, track source/version/SHA provenance, distinguish stale from current evidence, retain disagreements, ask narrow follow-up queries, and temporarily apply small externally documented deterministic rules for the current task.

## One deployment weight

`Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`

- size: **59,773,663 bytes**
- SHA-256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`
- neural parameters: **78,779,253**

R2.1 and R2.2 are zero-neural-parameter runtime upgrades, so a new weight is intentionally not created.

## R2.2 locked evidence — KFIGG-22

The final protocol was calibrated only on TRAIN. DEV and FRESH were not used for tuning.

| Split | R2.1 parent | R2.2 | Gain |
|---|---:|---:|---:|
| TRAIN 3000..3199 | 47.0% | **100.0%** | **+53.0 pp** |
| DEV 4000..4199 | 45.5% | **99.5%** | **+54.0 pp** |
| FRESH 5000..5199 | 51.0% | **100.0%** | **+49.0 pp** |

FRESH provenance/version integrity errors: **0**. Both systems use the same maximum evidence budget: top-k 2, at most 7 retrieval calls and at most 14 chunks.

FRESH 5000..5199 is consumed. The accepted R2.2 core source files are SHA-bound and frozen.

## What R2.2 adds over R2.1

R2.1 proved repeated retrieval between reasoning steps under a locked synthetic multi-hop benchmark. R2.2 adds an epistemic workspace on top:

1. retrieved evidence remains bound to immutable source/version/hash provenance;
2. newer evidence from the same source can supersede an older version without deleting history;
3. independent-source corroboration is distinguished from duplicated evidence;
4. contradictions remain visible instead of being silently overwritten;
5. unresolved beliefs produce targeted follow-up queries;
6. small externally documented deterministic rules can be used temporarily for the current task without being stored in neural weights.

This is a step toward the project goal of a compact neural core that can acquire relevant external knowledge when cognition needs it rather than memorizing the entire world inside parameters.

## Previous accepted evidence retained

R2.1a KFIGG-21 FRESH: retrieve-once **67%**, interleaved retrieval **100%**, +33 pp under the same four-chunk budget.

R2.0i FIGG-18 FRESH: frozen neural baseline **36.25%**, hybrid active-causal runtime **60.0%**, +23.75 pp; causal-prerequisite family **5% -> 100%**.

## Verification

- `research/R2_2_CURRENT_BEST.json` records current accepted provenance and consumed split.
- `scripts/verify_r22_release.py` checks locked source SHA values and accepted metadata.
- `.github/workflows/r22-integrity.yml` runs the integrity gate on GitHub Actions.
- GitHub Actions `R2.2 Integrity` is required to stay green before release claims are made.

Historical research tests that require intentionally removed split checkpoint binaries are not represented as green. The release continues to keep one current deployment weight.

## Scientific boundary

KFIGG-21 and KFIGG-22 are synthetic capability-isolation benchmarks. Their high scores do **not** mean Nolane is AGI or has complete world knowledge. Broad language ability, coding, mathematics, multimodal perception, open-world continual learning, long-horizon self-directed work and external benchmarks such as ARC-AGI-2, HLE/HLE-Verified, FrontierMath and Terminal-Bench remain incomplete or unmeasured.

The repository also does not claim superiority to >100B models without an actual matched-budget reference run.

## Key files

- `cogcoder/retrieval_microcycle.py` — cognition-time retrieval
- `cogcoder/knowledge_ledger.py` — provenance and contradiction retention
- `cogcoder/epistemic_workspace.py` — version-aware belief workspace
- `cogcoder/epistemic_program.py` — bounded provenance-bound documented-rule layer
- `cogcoder/r22_runtime.py` — R2.2 runtime integration
- `cogcoder/kfigg22.py` — locked R2.2 benchmark
- `research/R2_2_CURRENT_BEST.json` — accepted state
- `scripts/verify_r22_release.py` — integrity verifier

## GitHub binary boundary

GitHub `main` contains source, locks, results, manifests and CI. The current conversational GitHub connector still does not provide a practical local-binary/LFS/release-asset stream for the ~59.8MB `.pt`; therefore the repository keeps its exact SHA instead of pretending the binary is present. Milestone artifacts are also persisted to ChatGPT Library when available.

## License

Research code currently follows licenses embedded in imported/derived components. A repository-wide license should only be declared after those component licenses are audited.
