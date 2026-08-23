# Specification Acceptance Verifier

- AI ID: `verification.spec-acceptance.01`
- Role: specification and acceptance verification
- Rank: `specialist`
- Region: `verification-testing`
- Regional Chief: `verification.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-verification-testing-0.1`
- Private: `verification.spec-acceptance.01-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-verification-testing-0.1+verification.spec-acceptance.01-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+verification.spec-acceptance.01-delta-0.1`
- Physical parameters: shared 56,000,000 + local 8,000,000 = 64,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-verification-testing-0.1`
- Private version: `verification.spec-acceptance.01-EXT-0.0.0`
- Effective External Core bindings: fresh-sandbox, property-testing, fuzzer, integration-runner, acceptance-harness
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, fresh-sandbox, property-testing, fuzzer, integration-runner, acceptance-harness

## Personal State Namespaces

- Memory: `agent/verification.spec-acceptance.01`
- Skills: `skills/personal/verification.spec-acceptance.01`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
