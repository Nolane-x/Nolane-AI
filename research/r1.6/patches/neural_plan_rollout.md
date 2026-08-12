# R1.6 Compact Neural Plan Rollout

Date: 2026-08-12 (Asia/Bangkok)

## Goal

Replace scalar horizon heuristics with an explicit neural representation of future action structure. The planner predicts a **sequence of future dynamic actions** from the current System-2 thought and action-memory-enriched action set.

## Architecture

Planner dimension: **256**  
Planner horizon: **6**

Components:

```python
self.plan_state_projection = nn.Linear(workspace_dim, 256)
self.plan_action_projection = nn.Linear(workspace_dim, 256, bias=False)
self.plan_action_norm = nn.LayerNorm(256)
self.plan_step_embedding = nn.Parameter(torch.empty(6, 256))
self.plan_update = nn.GRUCell(256, 256)
self.plan_policy_scale = nn.Parameter(torch.tensor(0.0))
```

Rollout:

1. project current thought -> 256D plan state;
2. project every **dynamic enriched action** with one shared projection;
3. at each of 6 plan steps, score all actions by state/action compatibility;
4. softmax action distribution -> expected action embedding;
5. GRU updates latent plan state;
6. repeat.

The same action keys are reused at every horizon step, so permuting the action set permutes all plan logits identically. There are no fixed action-slot semantics.

The current policy receives only the first plan-step residual:

```python
tanh(plan_policy_scale) * plan_logits[:, 0]
```

`plan_policy_scale` starts at exactly zero, preserving parent behavior before training. Multi-step teacher losses will train the latent rollout.

## Verification

RED was observed before implementation: `plan_rollout` / `plan_horizon` did not exist.

After implementation and parameter-ceiling update:

```text
35 passed in 13.59s
```

Focused suite covers model behavior, checkpoint compatibility, and curriculum.

## Parameter accounting

- Plan-specific parameters: **724,737**
- Current experimental System-2 parameters: **20,739,854**
- Effective candidate: **70,268,531**
- New hard research ceiling: **75,000,000**

The ceiling was raised from 70M because the user explicitly authorized modest parameter growth. A hard ceiling remains; this is not unrestricted scaling.

## Source hashes

- `cogcoder/neural_system2.py`: `844f722c91773faefe1e7004860b70d319cbe90d3601109239f824dde1f80cc8`
- `cogcoder/neural_system2_training.py`: `69f1dfff0491b5b980a6d8e576a090cd8928102d6989a5309eaf8a2568f4eb36`
- `tests/test_neural_system2.py`: `f4e1d3a64d8d8cde609b6781a17024c51be1e0a38db9d173218c97470747ee26`
- R1.6 plan doc: `5a3f49ec1dfabce09b1c5725c43c34dfc4567a774dcf64a6dad5eabc14885974`

Fresh remains unopened. The planner is **not yet a capability win** until multi-step training and closed-loop dev evaluation are completed.
