# Recovery Agent

- AI ID: `reliability.recovery.01`
- Role: failure recovery and graceful degradation
- Rank: `specialist`
- Region: `performance-reliability`
- Regional Chief: `reliability.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-performance-reliability-0.1`
- Private: `reliability.recovery.01-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-performance-reliability-0.1+reliability.recovery.01-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+reliability.recovery.01-delta-0.1`
- Physical parameters: shared 56,000,000 + local 8,000,000 = 64,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-performance-reliability-0.1`
- Private version: `reliability.recovery.01-EXT-0.0.0`
- Effective External Core bindings: cpu-profiler, memory-profiler, race-detector, recovery-simulator, resilience-harness
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, cpu-profiler, memory-profiler, race-detector, recovery-simulator, resilience-harness

## Personal State Namespaces

- Memory: `agent/reliability.recovery.01`
- Skills: `skills/personal/reliability.recovery.01`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
