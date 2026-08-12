# Nolane AI — 50M Cognitive Architecture Research

Nolane AI is an experimental sub-50M-parameter neural cognitive system developed together with an external cognitive workspace and Habitat-style execution environment.

## Current research line

- **Neural core:** recurrent, weight-shared ~50M architecture.
- **R1.2:** Adaptive Cognitive Executive (ACE).
- **R1.3:** dynamic semantic action scorer + learned micro world-model.
- **R1.4:** semantic recurrent adapter (retained as a negative/ablation branch because it did not beat the R1.3 parent on its fresh gate).
- **R1.5:** public-observation System-2 cognitive workspace for hypothesis induction, evidence binding, causal system identification and planning.

## Research discipline

This repository treats benchmark integrity as part of the model. Fresh splits are locked before evaluation, hidden/internal fields are forbidden from policy inputs, and negative results are retained. The Frontier Generalization Gauntlet (FGG) uses exact verifiers rather than free-form LLM judging.

### Latest locked evidence

Fresh3 used 140 previously uninstantiated procedural tasks across seven arenas. The recorded controls were:

| Condition | Fresh3 result |
|---|---:|
| Oracle | 140/140 |
| Random | 12% overall |
| Neural without workspace | 60/140 (42.86%) |
| Workspace only | 137/140 (97.86%) |
| Full Nolane | 140/140 |

These results are **not** presented as proof of AGI. In particular, the workspace-only control shows that much of the System-2 capability currently lives in the cognitive architecture surrounding the neural core; the neural system provides measurable last-mile value but does not independently solve the hardest held-out arenas.

## Test status

The focused R1.3–R1.5 frontier suite is green (44/44 in the recorded local audit). R1.2/R1.1 regression gates are also green (24/24), and a critical legacy V5 subset is green (9/9). The historical full suite is currently not a clean gate because three legacy checkpoints are absent from the supplied milestone lineage:

- `checkpoints/dev-curriculum90.pt`
- `checkpoints/Nolane-Stage3.2-Candidate-Generator.pt`
- `checkpoints/Nolane-Stage3-Reconstructed-Generator-V1.pt`

The project does not fabricate replacement weights merely to make historical tests pass.

## Repository artifact layout

The full research source snapshot (code, tests, benchmark definitions, docs and evaluation evidence, excluding binary `.pt` weights and caches) is stored under `artifacts/` with a SHA-256 manifest. CI reconstructs the source tree from that immutable snapshot and runs the frontier integrity gates.

Large binary checkpoints remain provenance-bound by SHA-256 in milestone delivery packages because the connected GitHub interface used for this research session is not a bulk/LFS binary uploader. Future checkpoints should be published through Git LFS or release assets while preserving the hashes recorded by the research manifests.

## Benchmark inspiration

The evaluation philosophy borrows principles from ARC-AGI (first-seen fluid reasoning and exact success), SWE-bench/Terminal-Bench (reproducible executable verification), and modern agent benchmarks that require tool interaction and long-horizon state tracking. Nolane-specific tasks are procedural and seed-locked so benchmark answers cannot simply be memorized.

## License

Research code currently follows the licenses embedded in the imported/derived components. A repository-wide license should only be declared after those component licenses are audited.
