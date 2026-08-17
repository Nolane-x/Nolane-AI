# R2.53 → R2.54 Evolution

R2.53 externalized bounded cognitive procedures and objective deficit detection. R2.54 makes retrieval itself a first-class cognitive substrate rather than a single-source knowledge helper.

## New architecture

- Typed provenance-checked artifacts for facts, documentation, code, procedures, episodes, counterexamples, tools and representations.
- Multi-branch cognitive query compilation from deficits, unresolved requirements, symbols, context tags and required artifact kinds.
- Federated lexical/character-semantic/symbol/tag/kind/host-score retrieval with provenance-aware late fusion.
- Bounded multi-hop artifact graph over `calls`, `references`, `imports` and arbitrary typed relations.
- Temporal same-source supersession while preserving cross-source contradictions.
- Adaptive retrieval policy: narrow/deep structural retrieval, wide/shallow evidence retrieval, procedure-focused behavioral retrieval.
- Bounded cognitive attachments rather than indiscriminate prompt stuffing.
- Persistent cue→artifact association credit that can be strengthened by verified success and weakened by failure.
- Cognition-time R2.53 reflex bridge that can trigger even when model self-confidence is high.
- Safe retrieved behavioral manifests: SHA/trust/schema checks → R2.53 compilation → only registered primitives may execute.
- Dynamic external provider callbacks with failure isolation and explicit source-failure receipts.

## Adversarial corrections discovered during R2.54

1. One fixed top-k budget was wrong for all cognitive modes. R2.54 now routes retrieval policy by deficit type.
2. Same-source evidence repeated across query branches was initially miscounted as independent support. Independent support now requires distinct provenance URIs.
3. A real more-itertools transfer exposed that code graphs containing only direct calls miss functions passed as values, e.g. `partial(take, ...)`. The Python repository index now emits `references` edges in addition to `calls`.
4. External provider outages initially propagated through the whole fabric. Timeout/connection failures now fail open, remain visible in receipts, and healthy sources continue.

## Bounded evidence

- Focused R2.54 tests: 24/24.
- Protected local lineage R2.54→R2.41: 125/125 split across process groups.
- Frozen authored benchmark: 10/10 exact, 0 false accepts; single-shot lexical and fixed-top-k baselines 0/10.
- Safe retrieved procedure executes in 10/10 episodes; malicious unregistered `arbitrary.exec` manifest rejected 10/10; unsafe retrieved-content execution 0.
- Independently sourced more-itertools preview at commit `2fe1b2eeb9d75f994113fe3ac76d14b6bcd6fb10`: initial 1/2 exposed a representation gap; after the `references`-edge fix, 2/2 on the externally sourced code patterns. Clean hosted full-file replay remains required before acceptance.

## Claim boundary

R2.54 is not AGI and does not put outside knowledge into neural weights. It creates an inspectable external cognitive substrate that can behave like fast associative memory around a small model. Source trust, schemas, policy thresholds and the trusted primitive vocabulary remain partly host-designed; broad real-repository repair transfer and autonomous invention of new primitive semantics remain unresolved.
