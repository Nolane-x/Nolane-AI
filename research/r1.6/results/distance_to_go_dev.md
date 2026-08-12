# R1.6 Distance-to-Go — Dev Result

Date: 2026-08-12 (Asia/Bangkok)

## Candidate

- Parent: `Nolane-R1.6-NS2-CounterfactualWorld.pt`
- Train worlds: **90** (30/family)
- Train transitions: **621**
- Supervised action-distance targets: **1,692**
- Trainable parameters: **642**
- Distance MAE improved from ~0.52 to ~0.18-0.22
- Policy accuracy improved only marginally (~54.1% to peak ~54.8%)
- Candidate checkpoint: `Nolane-R1.6-NS2-DistanceToGo.pt`
- SHA-256: `0d61034e729816d87fd2143db4d3a522588971e78e706336c3055c826b7e8e64`
- Fresh: **not opened**

## Closed-loop dev

| Checkpoint | Refinement | Total | Causal | Rule | Resource |
|---|---:|---:|---:|---:|---:|
| CounterfactualWorld | 1 | **4/18** | 1/6 | 1/6 | 2/6 |
| CounterfactualWorld | 3 | **3/18** | 1/6 | 0/6 | 2/6 |
| DistanceToGo | 1 | **4/18** | 1/6 | 1/6 | 2/6 |
| DistanceToGo | 3 | **3/18** | 1/6 | 0/6 | 2/6 |

## Verdict

**REJECTED as a capability branch.** The scalar horizon target was learnable, but it did not create additional closed-loop solutions. This suggests the missing capability is more structured than a single notion of distance: the model needs explicit subgoal/precondition structure or a plan representation rather than only a scalar remaining-horizon estimate.
