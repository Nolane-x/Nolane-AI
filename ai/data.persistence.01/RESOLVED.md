# Persistence Agent

- AI ID: `data.persistence.01`
- Role: storage and persistence implementation
- Rank: `specialist`
- Region: `data-storage-migration`
- Regional Chief: `data.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-data-storage-migration-0.1`
- Private: `data.persistence.01-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-data-storage-migration-0.1+data.persistence.01-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+data.persistence.01-delta-0.1`
- Physical parameters: shared 56,000,000 + local 8,000,000 = 64,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-data-storage-migration-0.1`
- Private version: `data.persistence.01-EXT-0.0.0`
- Effective External Core bindings: schema-graph, migration-planner, consistency-checker, storage-profiler
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, schema-graph, migration-planner, consistency-checker, storage-profiler

## Personal State Namespaces

- Memory: `agent/data.persistence.01`
- Skills: `skills/personal/data.persistence.01`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
