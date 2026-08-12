# R1.6 Neural Plan Rollout — Dev Result

Date: 2026-08-12 (Asia/Bangkok)

## Candidate

- Parent: `Nolane-R1.6-NS2-CounterfactualWorld.pt`
- Train worlds: **90**
- Train current states: **621**
- Future-action labels: **2,437**
- Planner parameters: **724,737**
- Future plan accuracy: **20.23% -> 44.07%**
- Current-action accuracy: ~54.11% -> peak ~55.23%
- Candidate checkpoint: `Nolane-R1.6-NS2-NeuralPlan.pt`
- SHA-256: `d12bdbd7dd4f2fff7933a4e8727f4d2ccf4d2f6f2b36a0a6c1a7d8ced5bbafba`
- Effective candidate parameters: **70,268,531**
- Fresh: **not opened**

## Closed-loop dev

| Checkpoint | Refinement | Total | Causal | Rule | Resource | Mean steps |
|---|---:|---:|---:|---:|---:|---:|
| CounterfactualWorld | 1 | **4/18** | 1/6 | 1/6 | 2/6 | ~5.83 |
| CounterfactualWorld | 3 | **3/18** | 1/6 | 0/6 | 2/6 | — |
| NeuralPlan | 1 | **4/18** | 1/6 | 1/6 | 2/6 | **6.33** |
| NeuralPlan | 3 | **3/18** | 1/6 | 0/6 | 2/6 | **6.11** |

## Verdict

**REJECTED as a capability branch.** Multi-step future-action imitation became learnable, but it did not create additional closed-loop solutions and increased depth-1 episode length.

The key architectural limitation is now explicit: the rollout predicts a future action sequence while keeping the same latent world context. It therefore learns a sequence prior, not model-predictive planning. The next direction is closed-loop latent imagination where each imagined action updates an imagined state through the learned world model before the next action is selected.
