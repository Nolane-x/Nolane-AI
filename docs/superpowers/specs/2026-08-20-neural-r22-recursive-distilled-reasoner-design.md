# Neural R2.2 — Recursive Distilled Reasoner Design

## Goal

Increase the capability of the neural model itself, not the external R2.69/world/controller line. R2.2 must turn verified multi-step behavior into neural weights while keeping the model small and preserving the accepted Neural R2.1a release as an immutable control.

## Parent and claim boundary

- Parent control: Neural R2.1a frozen one-weight, SHA-256 `4f0b366e2401127e50b7fdbca651601b0a4b972004812c9f32043b82f0e3091b`.
- R2.1a delta remains byte-for-byte frozen.
- R2.2 is neural-only. External search/world/controller logic may generate verified teacher trajectories during training, but it is forbidden from the standalone candidate policy at evaluation.
- No AGI/frontier-equivalence claim. Promotion requires measured held-out neural-only gain.

## Architecture

R2.2 promotes the existing architecture-verified RecursiveLatentIntelligenceCore into a trained successor instead of adding another narrow router. The core uses one weight-shared reasoning cell for every latent iteration, so inference depth can increase without duplicating parameters. Inputs are public neural tensors already available to the R2.1a/R2.0e neural stack: state/context representations, action embeddings, parent/imagined/evidence effects, action memory, uncertainty/value, progress/budget/feedback, and the R2.1a base policy.

The R2.2 policy is residual over R2.1a. At initialization it must preserve parent action/stop/success outputs exactly. Training is allowed to earn residual changes only from verified supervision.

## Training

Stage A trains the recursive core while all parent modules are frozen. Each batch samples reasoning depth from 1–6. The loss combines:

1. symmetry-safe set-valued next-action supervision;
2. distillation from verified teacher action distributions;
3. anytime supervision across all emitted depths;
4. monotonic-depth regularization so later iterations are penalized for becoming worse than earlier ones;
5. counterfactual contrastive ranking between verified-compatible and incompatible actions;
6. effect/progress/uncertainty/stop/success auxiliary targets when public evidence supports them;
7. a ponder/halting target that predicts when sufficient reasoning has occurred;
8. parent-preservation loss on non-target families.

Stage B may jointly adapt the small R2.1a router and selected top executive parameters at a substantially lower learning rate. The large parent workspace is not blindly unfrozen; an upstream parameter must have a direct tested gradient path and its inclusion must improve dev performance without harming preserved families.

Only proof-verified teacher rows receive positive proof weight. Hidden role names/private benchmark fields must never enter deployment inputs.

## Evaluation protocol

The already-consumed R2.1a fresh range 900–919 is never used to tune R2.2. Development uses train/dev data only. Before the first R2.2 fresh evaluation, candidate weights and SHA-256 are frozen and a pre-fresh lock is written.

Fresh evaluation uses a new untouched FIGG-18 range beginning at index 1000, with the same environment, tensor construction, action budget, and controller shell for both R2.1a and R2.2. The external active-causal controller is disabled for both. Report per-family and total solved counts, steps, depth ablations at 1/2/4/8/12 iterations, calibration metrics, candidate SHA, and physical tensor parameter count.

## Promotion gate

R2.2 may replace CURRENT_BEST only if all conditions hold:

- total fresh solved count is strictly greater than R2.1a;
- causal-prerequisite solved count is not lower;
- no non-causal family loses more than one solved episode and aggregate non-causal solved count does not decrease;
- deeper inference has at least one verified beneficial operating point and does not produce non-finite values;
- fresh holdout was not used for post-hoc weight tuning;
- checkpoint round-trip and parent binding pass;
- physical parameter accounting is audited from the exact frozen artifact;
- Python 3.11 and 3.13 CI contracts pass on the exact PR head.

If the candidate fails the fresh gate, it remains research-only and R2.1a stays current best.

## Deliverables

- R2.2 neural policy/adapter and training code under `model/neural-r2.2/`.
- TDD contracts for residual no-op initialization, action permutation equivariance, shared-weight depth, adaptive halting bounds, set-valued/contrastive loss, checkpoint binding, parameter audit, and standalone evaluation isolation.
- Frozen delta/one-weight artifact only if training produces an admitted candidate.
- Pre-fresh lock, dev results, fresh result, parameter audit, SHA manifest, CI workflow, and release receipt.