# R2.67.1 Genuine Causal Necessity Hotfix — Design

## Status

Correctness continuation from merged R2.67 commit `43b43ce4b324b0d74357957af18dd0f60b1cb85e`.

R2.67.1 exists because independent hosted validation after the R2.67 freeze identified two release-invalidating defects:

1. probe-validation receipt units are inconsistent (`6 cases / 18 exact` for three probes over six contexts);
2. lower-order ablations reuse the full triplet union mask, so an omitted intervention's field remains hidden and can manufacture apparent three-probe necessity.

Hosted evidence:

- PR #58 / run `32199123145`: RED on Python 3.11 and 3.13 after accepted R2.66 passes first; successful R2.67 receipts report `probe_validation_cases=6`, `probe_validation_exact=18`.
- PR #59 / run `32199583627`: RED on Python 3.11 and 3.13 after accepted R2.66 passes first; every selected two-probe subset of the original tri-bilinear benchmark has an exact trusted-DSL reconstruction once free fields are recomputed for that subset, yet production grants three-probe authority.
- PR #60 / run `32199850422`: GREEN on Python 3.11 and 3.13 for a replacement cyclic family with information-theoretic singleton/pair collisions and autonomous three-probe discovery.

The merged R2.67 source/evidence lock therefore cannot serve as the final correctness boundary for the strong `strict lower-order falsification` claim.

## Corrected capability boundary

R2.67.1 may claim three-probe causal necessity only when every proper non-empty subset is tested with the evidence channels actually available under **that subset's own interventions**.

For an ablation subset `S`:

- expose one probe field for each intervention in `S`;
- hide only positions overwritten by interventions in `S`;
- expose all original positions untouched by every intervention in `S`;
- run the same declared trusted DSL and bounded synthesis policy;
- treat any budget exhaustion/incompleteness as inconclusive and fail closed;
- if any subset has an exact program, reject the three-probe necessity claim.

A full-triplet union mask may still be used for the full three-probe composition, but it is not a valid substitute for subset-specific lower-order evidence.

## Receipt accounting correction

`probe_validation_exact` counts probe observations, not validation contexts. Therefore `probe_validation_cases` must use the same unit:

`len(validation_contexts) * len(selected_probes)`.

For R2.67/R2.67.1 exactly three selected probes are required, so a successful six-context validation receipt must be `18 / 18`, never `18 / 6`.

Every early failure return after triplet selection must report the same planned probe-validation case unit. Before a triplet exists, the receipt may report zero probe cases because no probe-validation obligation has yet been created.

## Replacement authored family

Replace the six-field independent-dot family

`a*b + c*d + e*f`

with the cyclic three-field family

`F(a,b,c) = a*b + b*c + c*a`.

Authorize zero-valued one-field interventions on `a`, `b`, and `c`.

The three intervention observations are:

- zero `a`: `p_a = b*c`;
- zero `b`: `p_b = c*a`;
- zero `c`: `p_c = a*b`.

The full target is exactly:

`p_a + p_b + p_c`.

### Why this family is stronger

The authored corpus must contain explicit collision witnesses, not merely random examples.

For every pair of interventions, the field left free by that pair is set to zero in at least two rows while the hidden product varies. Example for `{a=0,b=0}`:

- `(a,b,c)=(1,2,0)` → pair evidence `(p_a,p_b,c)=(0,0,0)`, target `2`;
- `(a,b,c)=(2,3,0)` → same pair evidence `(0,0,0)`, target `6`.

Thus no deterministic expression language—not only the current bounded search—can reconstruct the target from that pair's legitimate evidence on the corpus. Symmetric witnesses exist for the other two pairs.

Singleton collision witnesses likewise hold the two visible original fields fixed while varying the hidden intervened field, proving singleton insufficiency.

This makes lower-order failure an information/evidence property rather than a scheduler/grammar artifact.

## Replacement external transfer

Retain pinned NumPy `2.4.6` and `numpy.dot`, but use the I/O-only adapter:

`numpy.dot([a,b,c], [b,c,a])`.

This equals the cyclic authored family exactly while preserving the external-source boundary. External discovery, validation, terminal, challenge, and heldout corpora must include the same collision structure where appropriate, plus independent asymmetric rows.

The source remains researcher-selected and I/O-only; this is not blind task discovery.

## Mandatory regressions before refreeze

R2.67.1 must freeze all of the following:

1. accepted R2.66 regressions remain green;
2. R2.67 ablation-budget incompleteness remains fail-closed;
3. probe receipt units are observation-consistent on every successful and post-selection failure path;
4. each singleton ablation recomputes its own free positions;
5. each pair ablation recomputes its own free positions;
6. original tri-bilinear family is rejected as a genuine three-probe-necessity witness under corrected subset semantics;
7. cyclic family has explicit information-theoretic collisions for every singleton and pair;
8. cyclic family full three-probe expression is exact;
9. engine discovers the cyclic family without a host-selected intervention triplet;
10. semantic rename and positional permutation invariance remain green;
11. terminal selected-probe re-observation remains green;
12. validator-before-oracle remains green;
13. semantic terminal disjointness remains green;
14. full oracle ledger remains exact;
15. pinned NumPy cyclic-dot external transfer passes challenge and heldout evidence;
16. false accepts remain zero;
17. trainable parameter delta remains zero.

## Evidence invalidation and release discipline

Because both production semantics and benchmark/evidence change, all existing R2.67 frozen artifacts are historical evidence only. R2.67.1 must not mutate them in place and pretend continuity.

Create fresh `R2_67_1_*` artifacts after production stops changing:

- pre-hosted source/evidence lock;
- authored Phase-A result;
- pinned external transfer result;
- hosted canonical verification record;
- release manifest/delivery boundary;
- complete repository bundle and SHA-256;
- post-merge exact-main verification.

The exact accepted R2.67 merge remains the parent and historical record; R2.67.1 supersedes its strong necessity claim.

## Non-goals

R2.67.1 still does not establish:

- arbitrary-N intervention scaling;
- adaptive sequential experiment policies;
- effectful/stateful interventions;
- unrestricted synthesis;
- blind external task discovery;
- broad coding autonomy;
- W5 convergence;
- frontier-model equivalence;
- AGI.
