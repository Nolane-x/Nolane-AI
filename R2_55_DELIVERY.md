# Nolane-AI R2.55 Delivery — Hardened Self-Improving Cognitive Acquisition

Status: **PENDING_HOSTED_ACCEPTANCE** until the clean capability commit and hosted R2.55 workflow are frozen in `R2_55_VERIFY_RESULT.json`.

## Capability boundary

R2.55 turns R2.54's federated cognitive retrieval fabric into a bounded acquisition lifecycle. External knowledge or procedures do not become trusted cognition merely because retrieval ranks them highly. Host-owned reliability, poisoning quarantine, independent challenge, lifecycle promotion, side-effect admission control, live rollback and trajectory distillation sit between retrieval and authority.

R2.55 adds **0 trainable parameters**. Distilled skills are external artifacts, not neural-weight updates. A host-issued content-addressed `AuthorityEnvelope` is minted before untrusted retrieval/tool data is observed; retrieved content may inform cognition but cannot mint or widen action or side-effect authority.

## Frozen authored adversarial benchmark

- Episodes: **10**
- R2.55 exact: **10/10**
- False accepts: **0**
- R2.54 baseline exact under poison-starved retrieval: **0/10**
- Poison quarantine: **10/10**
- Echo/Sybil collapse: **10/10**
- Safe procedure promotion after challenge: **10/10**
- Malicious compiled behavior quarantine: **10/10**
- Transactional live rollback after a fresh counterexample: **10/10**
- Successful trajectory distillation: **10/10**
- Distilled skill re-promotion through the normal lifecycle: **10/10**

## World-driven RED→GREEN hardening

Nolane World 0.5.0 found three material implementation weaknesses before release:

1. An internal 24-candidate cap could hide reliable evidence before the firewall. It was removed in favor of the host-configured acquisition budget.
2. Distilled skills could not re-enter the lifecycle because trust/support semantics made promotion unreachable. Two independently verifier-confirmed trajectories now provide distinct internal provenance episodes; challenge remains mandatory.
3. Working-state cloning was not a real sandbox for external side effects. Probation now rejects unsupported side-effect classes before execution; automatic probation is bounded to pure/state-only primitives.

## Independent prompt-injection transfer gate

Hosted acceptance additionally requires the official **InjecAgent** direct-harm/data-stealing datasets at pinned commit `f19c9f2c79a41046eb13c03c51a24c567a8ffa07`. The gate preserves user-tool utility while proposing every benchmark-labeled attacker tool through the R2.55 authority boundary and requires **zero authority escapes**. This is a control-plane containment test, not a claim that the underlying language model semantically detects every prompt injection.

## Nolane World boundary

World audit is valid, but W5 remains **FAIL** with score **0.0**. The blockers and unresolved unknowns are frozen in `research/R2_55_WORLD_FINAL.json`; this milestone does not claim World convergence.

## Remaining unknowns

- source/Sybil reliability attribution is heuristic;
- regex instruction filtering is not semantic prompt-injection immunity; the authority boundary limits consequences even when semantic detection fails;
- challenge suites can be incomplete or correlated with the acquired skill;
- arbitrary external I/O needs a real host sandbox/compensation layer;
- distillation remains bounded by registered primitive vocabulary;
- the R2.55 poisoning distribution is authored rather than a broad independent benchmark.

## Readiness

The final internal Coding-AGI engineering-readiness score is written only after clean hosted CI. It is an engineering rubric, **not AGI probability**.
