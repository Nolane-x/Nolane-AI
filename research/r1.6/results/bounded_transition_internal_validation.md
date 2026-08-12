# R1.6 Bounded Transition — Train-Internal Selection

Date: 2026-08-12 (Asia/Bangkok)

## Protocol

After the first bounded-transition candidate narrowly failed the old dev/persistence aggregate, hyperparameters were **not** tuned repeatedly on dev. A train-only internal protocol was created:

- procedural train pool: 20 tasks/family;
- fit: first 15/family = **45 worlds**, 303 transitions;
- internal validation: remaining 5/family = **15 worlds**, 102 transitions;
- parent representation/world features frozen;
- trainable transition parameters: **410,881**;
- objective: direct next-latent MSE only;
- optimizer: AdamW, lr 1.2e-3, weight decay 1e-5;
- 120 epochs, best selected solely by train-internal validation;
- fresh: unopened.

## Internal validation

- fit persistence MSE: `0.0043680`
- internal-val persistence MSE: `0.0040880`
- best internal-val candidate MSE: **`0.0033357`** at epoch 119
- ratio candidate/persistence: **0.81596**
- improvement over persistence: **18.40%**

Candidate checkpoint:

`Nolane-R1.6-NS2-BoundedTransitionInternal.pt`

SHA-256:

`94de757295368107099fd5d9060be2f617792d7e3da5c4bcf8b30d52260b1f0e`

Effective parameter accounting in the live experimental architecture: **70,269,172**.

Because it beat persistence without any dev feedback, the checkpoint was locked and advanced to a new dev transition gate.
