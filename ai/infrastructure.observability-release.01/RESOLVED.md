# Observability & Release Agent

- AI ID: `infrastructure.observability-release.01`
- Role: observability and release packaging
- Rank: `specialist`
- Region: `infrastructure-release`
- Regional Chief: `infrastructure.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-infrastructure-release-0.1`
- Private: `infrastructure.observability-release.01-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-infrastructure-release-0.1+infrastructure.observability-release.01-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+infrastructure.observability-release.01-delta-0.1`
- Physical parameters: shared 56,000,000 + local 8,000,000 = 64,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-infrastructure-release-0.1`
- Private version: `infrastructure.observability-release.01-EXT-0.0.0`
- Effective External Core bindings: ci-engine, container-runtime, deployment-controller, observability-stack, release-packager
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, ci-engine, container-runtime, deployment-controller, observability-stack, release-packager

## Personal State Namespaces

- Memory: `agent/infrastructure.observability-release.01`
- Skills: `skills/personal/infrastructure.observability-release.01`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
