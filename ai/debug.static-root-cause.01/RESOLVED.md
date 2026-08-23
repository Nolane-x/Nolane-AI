# Static Root-Cause Investigator

- AI ID: `debug.static-root-cause.01`
- Role: static defect and root-cause reasoning
- Rank: `specialist`
- Region: `debugging-failure`
- Regional Chief: `debug.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-debugging-failure-0.1`
- Private: `debug.static-root-cause.01-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-debugging-failure-0.1+debug.static-root-cause.01-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+debug.static-root-cause.01-delta-0.1`
- Physical parameters: shared 56,000,000 + local 8,000,000 = 64,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-debugging-failure-0.1`
- Private version: `debug.static-root-cause.01-EXT-0.0.0`
- Effective External Core bindings: runtime-tracer, stack-graph, coverage-graph, state-diff, crash-analyzer, git-bisect, failure-minimizer
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, runtime-tracer, stack-graph, coverage-graph, state-diff, crash-analyzer, git-bisect, failure-minimizer

## Personal State Namespaces

- Memory: `agent/debug.static-root-cause.01`
- Skills: `skills/personal/debug.static-root-cause.01`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
