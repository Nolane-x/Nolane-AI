# Dual-Role Causal Binder recovery candidate — train-only result

Date: 2026-08-12 (Asia/Bangkok)

This run repairs an earlier provenance inconsistency: GitHub recorded a completed Dual-Role gate, while the surviving recovery tree had no DualRole/CurrentBest checkpoint and the local gate JSON files were zero-byte. The candidate was therefore regenerated from the GitHub-preregistered protocol before any further R1.6 work.

## Protocol

- parent: `Nolane-R1.6-NS2-PSRPlanner.pt`
- train split only
- fit indices: 69–78 per family
- internal validation: 79–81 per family
- seed: 16082
- parent frozen; optimizer scope only `dual_role_*`
- compute-bounded recovery run: 20 epochs (the earlier 80-epoch attempt timed out at epoch 20 before saving and is not counted as an artifact)
- fresh remains unopened

## Internal result

Initial validation:
- CE: `1.0213709`
- accuracy: `52.727%`
- causal: `40.909%`
- resource: `73.913%`
- rule: `30.000%`

Best epoch 20:
- CE: `0.9991024`
- accuracy: `56.364%`
- causal: `40.909%`
- resource: `82.609%`
- rule: `30.000%`
- dual-role policy scale (`tanh(raw)`): `0.0234552`

Teacher-forced improvement is **not** treated as a capability win.

## Candidate artifact

- checkpoint: `Nolane-R1.6-NS2-DualRoleCausalBinder.pt`
- SHA-256: `1a7db1628ce3b5a4ba95c3ba0a8b1fb21d994042006042bb3903a0f60220de91`
- effective parameters under the current reconstructed source: `71,848,959`

## Machine gate rule

The candidate must solve **strictly more closed-loop tasks than PSRPlanner on both** held-out dev slices 54–59 and 60–65 per family. Otherwise PSRPlanner remains `CurrentBest`. No per-slice hyperparameter adjustment is allowed.