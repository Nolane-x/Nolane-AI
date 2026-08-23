# Reliability Chief

- AI ID: `reliability.chief`
- Role: Performance / Reliability Chief
- Rank: `chief`
- Region: `performance-reliability`
- Regional Chief: `reliability.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-performance-reliability-0.1`
- Private: `reliability.chief-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-performance-reliability-0.1+reliability.chief-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+reliability.chief-delta-0.1`
- Physical parameters: shared 56,000,000 + local 34,000,000 = 90,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-performance-reliability-0.1`
- Private version: `reliability.chief-EXT-0.0.0`
- Effective External Core bindings: cpu-profiler, memory-profiler, race-detector, recovery-simulator, resilience-harness
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, cpu-profiler, memory-profiler, race-detector, recovery-simulator, resilience-harness

## Personal State Namespaces

- Memory: `agent/reliability.chief`
- Skills: `skills/personal/reliability.chief`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
