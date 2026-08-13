# R1.9 Frontier-Generalization Design

## Objective

Evolve the recovered R1.8 parent without large parameter growth. The R1.9 milestone must improve a capability not already solved by the R1.8 one-step conditional-law head, preserve the accepted R1.8 lineage, and add a benchmark interface suitable for comparison with frontier models without claiming such a comparison before it is actually run.

## Immutable parent

- Parent checkpoint: `checkpoints/Nolane-R1.8-CCSM-ConditionalLaw.pt`
- Parent SHA-256: `400fc43ef46c9b6c7664703b49c0de7896b49eb728939423288b74847cb27c16`
- Parent effective parameters: 76,619,419
- All parent parameters are frozen during R1.9 training.

## Neural change

Add a standalone `FrontierRolloutHead` that predicts the residual error of a naive multi-step rollout. The head consumes only public representations already available to the model: current numeric state sketch, context fingerprint, dynamic action embeddings, the R1.8 one-step predicted effect for each program step, and an optional goal sketch. It uses one shared recurrent refinement cell across rollout positions and repeated refinement steps, so extra test-time reasoning depth does not duplicate parameters.

The head is a delta module rather than a rewrite of `NeuralSystem2Workspace`. A complete R1.9 model is the immutable R1.8 parent plus this delta. The target parameter budget is below 2.0M new parameters and below 79M effective parameters total.

## Internal training benchmark

`FIGG-19 Rollout` is generated procedurally from the four R1.8 causal families. For each public state, it constructs two-step counterfactual programs from non-submit actions and computes the exact final public state delta by simulator branching. The R1.8 parent supplies one-step effects. The baseline is the additive composition of those parent effects; the R1.9 head learns only the residual needed to predict the true two-step delta.

Training uses only the `train` split. Fit and internal-validation indices are disjoint and preregistered. `dev` remains unopened until the checkpoint is frozen; `fresh` remains unopened until a post-DEV pre-fresh lock binds checkpoint, split, and evaluator settings. No parameter or model/evaluator code tuning is allowed after fresh is consumed.

Acceptance requires:

1. candidate two-step MSE below the same-row additive R1.8 baseline;
2. improvement in every benchmark family, not only aggregate;
3. exact parent freeze verified by parameter-name and tensor-digest checks;
4. R1.8 regression tests remain green;
5. action permutation equivariance of the new head;
6. total effective parameter count below 79,000,000.

## Frontier benchmark interoperability

Add `benchmarks/frontier100b/` as an evaluation contract, not as a source of unverified capability claims. It records primary-source benchmark families and exact scoring interfaces for:

- ARC-AGI-2: exact grid match, pass@2-compatible task accounting;
- Humanity's Last Exam / HLE-Verified: closed-answer exact/normalized scoring;
- FrontierMath-style tasks: verifier-backed answer checking when a verifier is supplied;
- Terminal-Bench / HLCE-style coding tasks: executable tests in a sandbox or user-provided judge.

The repository does not vendor private benchmark data or claim that FIGG-19 is proven hard for >100B models. A `>100B-hard` label may be attached only after a named >100B reference model is run under the locked harness and its score is recorded with model/version/budget.

## Weight publication

The connected GitHub interface can publish text source/manifests directly. Its Git Data surface exposes blob primitives, but serializing 92–108MB checkpoints through model-mediated base64 arguments is not a practical or reliable binary publication path, and no LFS/release-asset upload action is exposed. Therefore this milestone will:

- keep complete real weights inside the delivery ZIP and ChatGPT Library;
- publish SHA-256, size, parent binding, and reconstruction manifest to GitHub;
- include a Git LFS publication script and `.gitattributes` for a normal git environment;
- never replace real weights with fabricated placeholders.
