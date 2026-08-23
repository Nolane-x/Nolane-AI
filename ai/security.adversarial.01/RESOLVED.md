# Adversarial Security Agent

- AI ID: `security.adversarial.01`
- Role: adversarial security validation
- Rank: `specialist`
- Region: `security-adversarial`
- Regional Chief: `security.chief`

## Neural Core

- Shared: `NUC-0.1`
- Regional: `REGION-security-adversarial-0.1`
- Private: `security.adversarial.01-delta-0.1`
- Resolved composition: `NUC-0.1+REGION-security-adversarial-0.1+security.adversarial.01-delta-0.1`
- Accepted runtime neural version: `NUC-0.1+security.adversarial.01-delta-0.1`
- Physical parameters: shared 56,000,000 + local 8,000,000 = 64,000,000

## External Core

- Shared version: `EXT-0.1`
- Regional version: `REGION-EXT-security-adversarial-0.1`
- Private version: `security.adversarial.01-EXT-0.0.0`
- Effective External Core bindings: threat-model, security-scanner, attack-harness, supply-chain-auditor
- Effective tool permissions: filesystem, git, terminal, code-search, memory, task-graph, event-ledger, evidence-store, threat-model, security-scanner, attack-harness, supply-chain-auditor

## Personal State Namespaces

- Memory: `agent/security.adversarial.01`
- Skills: `skills/personal/security.adversarial.01`
- Authority scope: task

> GENERATED VIEW — edit canonical shared/region/profile source, never this file.
