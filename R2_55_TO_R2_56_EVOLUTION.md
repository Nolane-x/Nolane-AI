# R2.55 → R2.56 Evolution

R2.55 learned and hardened external knowledge/procedures, but its distilled behaviors were bounded by the operator vocabulary already registered by the host. R2.56 introduces a separate invention path for a missing **pure** primitive.

## What changed

1. **Pure expression DSL** — canonical, content-addressed expression trees with a closed effect-free opcode table.
2. **Bounded synthesis** — deterministic minimum-cost search over declared fields/constants with semantic-vector deduplication.
3. **Independent challenge gate** — training fit never grants promotion. Empty challenge suites fail closed.
4. **CEGIS refinement** — a failed challenge is quarantined and may become a bounded counterexample for a fresh candidate.
5. **Child-registry promotion** — a successful invention becomes `invented.<digest>` without mutating the parent registry before promotion.
6. **Live rollback** — evaluator/type/post-promotion failures restore `ExternalWorkingState` and move the invention to `rolled_back`.
7. **Authority preservation** — invention does not mint action authority; R2.55 `AuthorityEnvelope` remains host-owned.
8. **Independent oracle transfer** — Boltons `clamp` is used only as an I/O oracle; the learner induces behavior without parsing its implementation.

## What did not change

- Neural weights are unchanged.
- Arbitrary Python is not an invention target.
- No external side-effect class can be invented.
- No claim of Turing-complete/open-ended synthesis is made.
- Nolane World W5 remains non-converged.

## Next falsification frontier

The highest-value next frontier is **meta-invention of the representation/operator vocabulary itself** or safe host-sandboxed effectful operator construction, but only with external repository-level tasks where the current R2.56 finite grammar provably abstains/fails and the next mechanism causes a reproducible improvement.
