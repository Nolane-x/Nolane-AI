# R1.6 Conservative Causal-Memory Policy Residual

Date: 2026-08-12 (Asia/Bangkok)

## Motivation

Breadth-first memory/world training caused catastrophic interference: delayed-resource improved while causal/rule wins disappeared. This feature therefore leaves the parent semantic/context/world policy intact and adds a **small evidence-gated residual** that can only act through dynamic action-memory.

## Architecture

New trainable components:

```python
self.causal_memory_policy_key = nn.Linear(workspace_dim, workspace_dim, bias=False)
self.causal_memory_policy_scale = nn.Parameter(torch.tensor(0.0))
```

Core scorer:

```python
def causal_memory_policy_bonus(self, thought, action_memory, action_counts):
    memory_workspace = self.action_memory_projection(action_memory)
    query = self.policy_query(thought).unsqueeze(1)
    keys = self.causal_memory_policy_key(memory_workspace)
    match = (query * keys).sum(dim=-1) / math.sqrt(self.workspace_dim)
    evidence_gate = 1.0 - torch.exp(-action_counts.clamp_min(0.0))
    scale = torch.tanh(self.causal_memory_policy_scale)
    return scale * evidence_gate * match
```

The bonus is added only to `no_imagination` / `full` policy paths, not the `semantic_only` ablation.

## Safety / compatibility properties

- `causal_memory_policy_scale` starts exactly at zero, so before training the new branch contributes exactly zero to every action.
- Actions with zero evidence count receive exactly zero bonus even after the global scale is nonzero.
- The same key transform is shared over all dynamic actions; there is no fixed slot semantic.
- The residual is action-permutation equivariant.
- Legacy R1.6 checkpoints are loadable with the new parameters listed as allowed missing keys.

## TDD evidence

RED was observed first: tests failed because `causal_memory_policy_bonus` and `causal_memory_policy_scale` did not exist.

After implementation/refactor:

```text
23 passed in 3.31s
```

Focused files: `tests/test_neural_system2.py` + `tests/test_neural_system2_training.py`.

## Parameter accounting

- Current System-2 parameters: **20,014,475**
- R1.2 effective parent accounting: **49,528,677**
- Candidate total if this residual is retained: **69,543,152**

This remains a modest-size model relative to billion-parameter LLMs. The feature is **not yet a capability win**; it must be trained/evaluated and will be rejected if it does not beat the 4/18 closed-loop dev parent without damaging other families.

## Source integrity after feature implementation

- `cogcoder/neural_system2.py`: `be8c4a03793db8694a6a2babe9b2676f107af24be47646c73a27bce9ae47289f`
- `cogcoder/neural_system2_training.py`: `211eb228867fd3b2262cd6b6c9aeb235d30dfacdbc95a1fdb00f8963116be4e4`
- `tests/test_neural_system2.py`: `4f3029a55e8adf8c92b7ad25398d65a7990c2668995fb378959c1a91ff06d434`

Fresh remains unopened.
