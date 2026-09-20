# Neural vNext Native R13 — selective neural causal residual

Status: **DEVELOPMENT ONLY; confirmation/fresh UNOPENED**.

R12 proved that a learned causal residual can improve one dev court and still reverse sign on a disjoint confirmation court. R13 therefore changes the mechanism rather than retuning R12.

R13 trains a neural causal residual on one train-only range, then selects a **minimum override margin** on a disjoint train-only calibration range. At inference, a neural proposal may override accepted R11 only when its proposal-vs-R11 logit margin exceeds that calibrated threshold.

The threshold is selected without dev/fresh data. It must achieve at least 90% precision against train-only oracle actions; otherwise overrides are disabled.

## Locked identities

- residual training: `train:4096..4479`
- train-only calibration: `train:4480..4607`
- primary dev: `dev:672..703`
- confirmation: `dev:704..735`
- reserved fresh: `fresh:280..319`
- consumed fresh: `0..279`

Visible targets return exact frozen R4 logits. Inference uses public evidence only.
