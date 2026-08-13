# R2.2 Epistemic Program Workspace Design

## Goal
Extend accepted R2.1a cognition-time retrieval into a persistent zero-parameter epistemic workspace that can reconcile changing/contradictory evidence, preserve provenance, identify missing knowledge, and compile externally documented declarative rules into temporary executable microprograms without storing that knowledge in neural weights.

## Constraints
- Parent deployment remains the accepted 78,779,253-parameter R2.0i one-weight.
- R2.2 adds 0 neural parameters by default.
- With no external knowledge source or no compiled program, R2.0i/R2.1 behavior must remain unchanged.
- Every accepted belief/rule must be traceable to immutable evidence chunk SHA/version/source metadata.
- Contradictions are retained; they are never silently deleted.
- Newer versions from the same source supersede older versions for current-belief queries, while historical queries can still inspect old versions.
- Independent-source corroboration must be distinguishable from duplicate copies of the same source.
- FRESH is opened once after TRAIN and DEV admission; source hashes are locked before each gate.

## Architecture
1. **Epistemic claim layer** parses retrieved evidence into normalized claims while retaining raw chunks.
2. **Temporal/version resolver** groups claims by `(subject, relation, source_uri)` and marks newer versions as current while preserving older provenance.
3. **Belief fusion layer** ranks competing objects by recency, source trust, retrieval score, and independent-source corroboration; unresolved near-ties remain contested.
4. **Missing-knowledge planner** emits targeted follow-up queries from unresolved claim slots instead of broad prompt stuffing.
5. **Rule compiler** accepts a narrow, explicit external rule DSL carried in evidence and produces temporary typed microprograms. Programs are never written to neural weights and carry the evidence SHAs that authorized each instruction.
6. **R2.2 runtime** wraps R2.1. It exposes retrieval, belief queries, rule compilation/execution, and an optional generation hook. Disabling R2.2 features preserves R2.1/R2.0i behavior.

## Benchmark: KFIGG-22 Dynamic Epistemic Programs
Each case contains a 2-4 hop reasoning chain mixed with distractors, stale higher-trust documents, newer lower-trust corrections, independent corroboration, and optional externally documented deterministic rules. The answer is never exposed in hidden solver state. The accepted comparison is R2.1a interleaved retrieval versus R2.2 epistemic reasoning under the same maximum retrieval-call and chunk budgets.

Admission thresholds:
- TRAIN gain >= 10 percentage points over R2.1a interleaved.
- DEV gain >= 10 pp and provenance failures = 0.
- FRESH gain >= 10 pp, provenance failures = 0, and no version-resolution corruption.
- No post-FRESH tuning of accepted core source.

## Claim boundary
Passing KFIGG-22 proves bounded zero-parameter dynamic evidence integration and temporary rule execution on the locked benchmark. It is not proof of AGI, general language understanding, unrestricted code execution, or superiority to >100B models.
