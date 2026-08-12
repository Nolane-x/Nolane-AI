# R1.6 Breadth-First Memory -> World -> Plan — Dev Result

Date: 2026-08-12 (Asia/Bangkok)

## Training

- Parent: `Nolane-R1.6-NS2-CounterfactualWorld.pt`
- Train split: 20 tasks/family = **60 procedural worlds**
- Teacher transitions: **405**
- Frozen Stage-2 perception collected with the new batched curriculum path
- Trainable pathway: structured-delta + effect/feedback encoder + dynamic action-memory + action-key/world-action + progress/information/failure + policy residual
- Trainable parameters: **1,783,044**
- Optimizer passes: **1 epoch**
- Trajectory action accuracy: **57.28%**
- Checkpoint: `Nolane-R1.6-NS2-BreadthMemory.pt`
- SHA-256: `db6085076d0869b955e0dc2eea311070a97f70746397e4dee880e82f5039b8d8`
- Fresh: **not opened**

## Closed-loop dev

| Checkpoint | Refinement | Total | Causal | Rule | Resource |
|---|---:|---:|---:|---:|---:|
| CounterfactualWorld | 1 | **4/18** | 1/6 | 1/6 | 2/6 |
| CounterfactualWorld | 3 | **3/18** | 1/6 | 0/6 | 2/6 |
| BreadthMemory | 1 | **3/18** | 0/6 | 0/6 | 3/6 |
| BreadthMemory | 3 | **3/18** | 0/6 | 0/6 | 3/6 |

## Verdict

**REJECTED as a capability candidate.** The broader one-pass curriculum improved delayed-resource behavior but erased the parent's causal-identification and compositional-rule wins. `CounterfactualWorld` remains the strongest stable parent at 4/18.

**Infrastructure result retained:** batched Stage-2 curriculum encoding made the 60-world run complete cleanly instead of timing out, so future breadth experiments can scale without changing benchmark semantics.
