# R2.5 Reality Report

R2.5 tested a zero-neural-parameter ARC-AGI-2 program-synthesis runtime on the official corpus pinned at `f3283f727488ad98fe575ea6a5ac981e4a188e49`.

The candidate was frozen before the public scoring run. The immutable candidate commit is `bc390a9f6659493ecf1741aeda7bcb3d04ecd4d4`; the lock commit is `6cf7413420dd0f37cea3c39d9feeb17275c0ae1e`.

Development on the 1,000-task training split reached **76/1000 = 7.6%** with two attempts per test input and a 64-program cap. The frozen 120-task public scoring run produced **0/120 = 0.0%**, with zero runtime errors and zero exact candidate programs on average. GitHub Actions run: `31756672804`.

This is a negative external result. It shows that the typed DSL and exact-consistency search learned useful coverage on the public training distribution but did not transfer to the ARC-AGI-2 public scoring distribution. R2.5 is therefore **not promoted** over R2.4 as a broad-reasoning upgrade.

The accepted system remains **R2.4 Long-Horizon Replanning** with **78,779,253 neural parameters**. R2.5 adds zero neural parameters. The internal AGI-readiness rubric remains **18.2/100**; it is not an AGI probability.

The 120-task public score is preserved as final R2.5 evidence and is not used for post-hoc tuning of the frozen R2.5 candidate. Future research must use training-only evidence, a new protocol, or another independent held-out benchmark rather than optimizing R2.5 against this consumed score.
