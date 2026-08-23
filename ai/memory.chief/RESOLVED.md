# Memory & Context Chief

- AI ID: `memory.chief`
- Role: Memory / Context / Knowledge Chief
- Rank: `chief`
- Region: `memory-context-knowledge`
- Regional Chief: `memory.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-memory-context-knowledge-0.1`
- Private: `memory.chief-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-memory-context-knowledge-0.1+memory.chief-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+memory.chief-delta-0.1`
- Physical parameters: shared 56,000,000 + local 34,000,000 = 90,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-memory-context-knowledge-0.1`
- Private version: `memory.chief-EXT-0.0.0`
- Effective External Core bindings: vector-retrieval, knowledge-graph, temporal-memory, skill-store, context-compiler, semantic-diff
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, vector-retrieval, knowledge-graph, temporal-memory, skill-store, context-compiler, semantic-diff

## Personal State Namespaces

- Memory: `agent/memory.chief`
- Skills: `skills/personal/memory.chief`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
