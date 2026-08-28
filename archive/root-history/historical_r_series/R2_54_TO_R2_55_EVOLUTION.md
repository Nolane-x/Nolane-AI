# R2.54 → R2.55 Evolution

R2.54 made retrieval a cognition-time substrate. R2.55 adds an acquisition lifecycle so retrieved knowledge and behavior are not automatically trusted or executable merely because they rank highly.

## Architectural evolution

- Host-owned source reliability caps self-declared artifact trust.
- Near-duplicate echo/Sybil swarms are collapsed before structured claim voting.
- Instruction-like retrieved payloads are quarantined before they shape cognition.
- Structured claim conflicts are resolved with reliability-weighted independent support, not raw retrieval count.
- Acquisition policy can spend the host-configured retrieval budget instead of an internal magic cap.
- Association credit can decay so stale external synapses are forgotten.
- Retrieved procedures move candidate → probation → promoted, or quarantine/rolled_back.
- Promotion requires a host-side challenge suite independent from the retrieved procedure's own verifier.
- Automatic probation is limited to pure/state-only registered primitives; unsupported external side-effect classes are rejected before execution.
- Live execution is transactional for ExternalWorkingState and rolls back on a new counterexample.
- Successful verifier-confirmed trajectories can be distilled into procedure artifacts outside model weights.
- Distilled procedures remain non-authoritative and must re-enter support/challenge/promotion before use.
- Host-issued content-addressed authority envelopes separate the data plane from the control plane: untrusted retrieval/tool content cannot mint or widen action scope or side-effect classes.
- A narrowed child authority envelope can only remove capabilities, never add them.

## World-driven hardening

Nolane World 0.5.0 exposed three concrete failures that became RED→GREEN regressions:

1. An internal 24-candidate acquisition cap could hide correct evidence before the firewall. R2.55 now consumes the host-configured acquisition budget.
2. Distilled skills could not re-enter the normal lifecycle because trust/support semantics made promotion unreachable. Independent verifier-confirmed trajectories are now separate internal provenance episodes, while challenge remains mandatory.
3. Cloning working state was not a real sandbox for external I/O. Probation now rejects unsupported side-effect classes before the executor; arbitrary external effects remain a future host-sandbox problem rather than something falsely claimed to be rollback-safe.

## Frozen authored adversarial benchmark

- 10 episodes.
- R2.55 exact: 10/10; false accepts: 0.
- R2.54 baseline exact: 0/10 under the same poison-starved acquisition setup.
- Every R2.55 episode requires poison quarantine, echo collapse, malicious compiled behavior quarantine, safe procedure promotion, transactional rollback after a fresh live counterexample, successful trajectory distillation, and re-promotion of independently verifier-confirmed distilled skill artifacts through the normal lifecycle.
- Added trainable parameters: 0.

## Independent external gate

Hosted acceptance is additionally conditioned on all four official InjecAgent dataset families at commit `f19c9f2c79a41046eb13c03c51a24c567a8ffa07`. The runtime pre-authorizes the benchmark user tool before the untrusted tool response is observed and then must reject every benchmark-labeled attacker-tool proposal without blocking the intended user tool. This demonstrates host-side authority containment under independently sourced indirect prompt injection; it does **not** prove model-level semantic prompt-injection immunity.

## Remaining claim boundary

R2.55 does not prove semantic prompt-injection immunity, globally reliable Sybil/source attribution, a complete challenge oracle, real rollback of arbitrary external side effects, open-ended primitive invention, or broad real-world poisoning robustness. The authored benchmark is not a substitute for an independently sourced adversarial distribution.

## Hosted acceptance outcome

Clean GitHub hosted run `32088996853` passed the complete R2.55 gate at commit `0621a43172fff1355bebee3c09922922c49f67c4`, including 19/19 focused tests, the full protected R2.55→R2.41 lineage (144/144 relevant tests), Python 3.11 and 3.13, authored evidence recomputation, and the pinned InjecAgent external transfer. InjecAgent yielded 2,108 cases, preserved 2,108 intended user-tool authorizations, blocked 3,196/3,196 attacker-action proposals and produced zero authority escapes. Readiness therefore moves conservatively from 45.5 to 46.0/100.
