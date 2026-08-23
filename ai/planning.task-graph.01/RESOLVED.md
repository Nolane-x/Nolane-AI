# Task Graph Planner

- AI ID: `planning.task-graph.01`
- Role: task decomposition and dependency planning
- Rank: `senior_specialist`
- Region: `planning-program`
- Regional Chief: `planning.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-planning-program-0.1`
- Private: `planning.task-graph.01-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-planning-program-0.1+planning.task-graph.01-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+planning.task-graph.01-delta-0.1`
- Physical parameters: shared 56,000,000 + local 20,000,000 = 76,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-planning-program-0.1`
- Private version: `planning.task-graph.01-EXT-0.0.0`
- Effective External Core bindings: task-dag, critical-path-engine, risk-graph, progress-reconciler
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, task-dag, critical-path-engine, risk-graph, progress-reconciler

## Personal State Namespaces

- Memory: `agent/planning.task-graph.01`
- Skills: `skills/personal/planning.task-graph.01`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
