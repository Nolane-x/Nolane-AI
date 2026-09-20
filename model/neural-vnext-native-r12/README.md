# Neural vNext Native R12 — neural causal residual

Status: **DEVELOPMENT ONLY; confirmation/fresh UNOPENED**.

R12 is the first successor after accepted R11 that deliberately moves successful causal reasoning back into the **learned Neural Core**.

Accepted R11 remains the immutable behavioral fallback. R12 adds a trainable hidden-goal residual that receives only public/inference-safe features:

- frozen R4 neural action representation and recurrent hidden state;
- frozen R4 latent-goal embedding;
- public progress-derived goal posterior and marginals;
- certified R11 causal per-action features;
- the accepted R11 action identity.

The final residual layer is zero-initialized. On hidden targets, an untrained R12 therefore chooses the accepted R11 action. On visible targets R12 returns exact frozen R4 logits. When public goal support is broader than the candidate's preregistered support gate, the residual is disabled.

Private benchmark information is not an inference input. Train-split oracle actions are used only as supervision.

## Locked identities

- train: `train:3584..4095` (implicit-goal only)
- primary dev: `dev:608..639`
- confirmation: `dev:640..671`
- reserved fresh: `fresh:280..319`
- consumed fresh: `0..279`

Promotion requires strict total + implicit-goal solved gain over accepted R11 with exact visible-target family solved counts.
