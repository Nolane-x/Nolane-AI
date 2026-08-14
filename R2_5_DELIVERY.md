# R2.5 Delivery — ARC External Evidence

R2.5 is complete as an external-evidence research milestone and is **not promoted** over R2.4.

## Frozen evidence

- Neural parameters: **78,779,253**
- R2.5 new neural parameters: **0**
- ARC-AGI-2 revision: `f3283f727488ad98fe575ea6a5ac981e4a188e49`
- Frozen candidate commit: `bc390a9f6659493ecf1741aeda7bcb3d04ecd4d4`
- Freeze lock commit: `6cf7413420dd0f37cea3c39d9feeb17275c0ae1e`
- TRAIN: **76/1000 = 7.6%**
- Frozen public scoring: **0/120 = 0.0%**
- Public scoring run: `31756672804`
- Exact frozen TRAIN integrity run: `31756832723` — PASS
- Current accepted system remains **R2.4 Long-Horizon Replanning**.
- Internal readiness rubric remains **18.2/100**.

## Complete artifact

`Nolane-R2.5-ARC-External-Evidence-COMPLETE-2026-08-14.zip`

- size: **55,297,389 bytes**
- entries: **1,078**
- archive test: PASS
- `.pt` files: **exactly 1**
- SHA-256: `c7b945fe7535f15076e528d2caede210ac07723e9302579bc8cb145db9d5aaae`

The one deployment weight remains `Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`, SHA-256 `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`.

## Recovery

Persistent recovery copies are stored under:

`/Nolane/R2.5-ARC-External-Evidence/FINAL/`

The folder contains the COMPLETE ZIP, ZIP checksum, one-weight file and weight checksum.

## Scientific boundary

The frozen public ARC-AGI-2 score is a negative external result and is preserved without post-hoc R2.5 tuning. The result does not support a claim of broad ARC competence, AGI, or superiority to frontier or >100B models. Future broad-reasoning research should use a new protocol and independent held-out evidence rather than optimize R2.5 against the consumed public score.
