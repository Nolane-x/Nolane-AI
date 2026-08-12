# R1.6 Contrastive Effect -> PSR — Closed-Loop Gate

Date: 2026-08-12 (Asia/Bangkok)

Untouched slice: **dev indices 42-47/family**, 18 interactive worlds.

| Checkpoint | Total | Causal | Resource | Rule | Mean steps |
|---|---:|---:|---:|---:|---:|
| same-source PSRPlanner, effect projection=0 | **3/18** | 0/6 | 3/6 | 0/6 | 7.0556 |
| ContrastiveEffectPSR | **3/18** | 0/6 | 3/6 | 0/6 | 7.1111 |

Causal mean steps increased from 10.8333 to 11.0 without producing a solution.

## Verdict

**TRAINED CONTRASTIVE EFFECT PROJECTION REJECTED.**

The parameter-free contrastive effect representation remains a valid diagnostic/infrastructure primitive, but a 32,768-parameter projection into the existing PSR action representation has now failed two independent closed-loop gates (raw effect and contrastive effect). The final retained policy remains `Nolane-R1.6-NS2-PSRPlanner.pt`.

Rejected checkpoint:

- `Nolane-R1.6-NS2-ContrastiveEffectPSR.pt`
- SHA-256: `f67572dd20665148e946353826f93ccae33f9e30a446b8b661b78d6f41cfa142`

## Next direction

Use the observed causal effect as an **attention query over current public structured atoms** rather than merely perturbing the PSR action embedding. This should let the model explicitly bind an opaque actuator's observed effect to the relevant current/goal fields before producing a zero-initialized policy residual.

Fresh remains unopened.
