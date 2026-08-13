# Nolane AI — R2.1a Cognition-Time Retrieval Fabric

Nolane AI is an experimental compact cognitive system built around a small neural core plus explicit memory, verification, active experimentation and external knowledge access. The repository preserves rejected branches and separates **neural capability** from **hybrid runtime capability** rather than attributing runtime gains to the weight itself.

## Current accepted system

The current neural stack remains **78,779,253 effective parameters**:

- R1.9 FrontierRollout parent: **78,214,173** effective parameters.
- R2.0e EvidenceEffect executive: **+565,080** parameters.
- R2.0i Active Causal Discovery: **+0 neural parameters**.
- R2.1a Cognition-Time Retrieval Fabric: **+0 neural parameters**.

R2.0i remains the accepted active-causal controller. R2.1a adds an opt-in external knowledge fabric that can retrieve **between cognition/generation steps**, revise later queries from evidence just retrieved, keep provenance, retain contradictions and stop retrieval under explicit call/character budgets. With no knowledge source attached, R2.1 calls the frozen R2.0i runtime directly.

The design goal is not to force world knowledge into the neural weights. The compact neural system can instead acquire task-relevant external evidence when it becomes useful during an ongoing reasoning/generation trajectory.

## Current deployment artifact: ONE weight

Use the same single checkpoint:

`Nolane-R2.0i-78.8M-STRONGEST-ONE-WEIGHT.pt`

- size: **59,773,663 bytes**
- SHA-256: `b1c2be66b6d42cc34b62a1c0960e47b13525d68126fa038b2ce9a11980b7f20e`
- effective neural parameters: **78,779,253**
- R2.1 new neural parameters: **0**

R2.1 is a runtime upgrade rather than a new neural checkpoint. `CURRENT_ONE_WEIGHT_R2_0I.json` remains the canonical weight manifest; `research/R2_1_CURRENT_BEST.json` is the current accepted system manifest.

## R2.1 locked retrieval evidence — KFIGG-21

KFIGG-21 isolates a specific capability: whether an agent can retrieve new evidence *during* a multi-hop reasoning trajectory rather than performing one static retrieval before reasoning begins.

Both methods receive the same maximum evidence budget of **4 chunks**:

- **retrieve-once:** one initial query, up to four chunks;
- **interleaved:** up to four retrieval calls, one chunk per call; every later query may use only the original task and evidence already retrieved.

| Split | Retrieve once | R2.1 interleaved | Gain |
|---|---:|---:|---:|
| TRAIN gate — 200 cases | 68.0% | **100%** | **+32.0 pp** |
| DEV — 200 cases | 66.5% | **100%** | **+33.5 pp** |
| FRESH 2000..2199 — 200 cases | 67.0% | **100%** | **+33.0 pp** |

FRESH provenance failures: **0**. Median retrieved characters among solved cases: **108 retrieve-once vs 81 interleaved**, ratio **0.75**.

Descriptively on the consumed FRESH split, retrieve-once solved all 2-hop and 3-hop cases but **0/66 four-hop cases** under the locked four-chunk budget; interleaved solved **200/200** total cases. The mechanism is that later-hop entities cannot be targeted until earlier evidence reveals them.

FRESH 2000..2199 is now **consumed**. The six accepted R2.1 core source files are SHA-bound; no post-FRESH tuning is allowed for this claim.

## How cognition-time retrieval works

The accepted runtime is deliberately backend-agnostic:

1. the current cognitive/generation state emits a knowledge need plus uncertainty/query-drift signals;
2. the retriever decides whether another lookup is justified;
3. returned chunks are bound to source URI, version, byte range and SHA-256;
4. evidence enters an append-only ledger that retains conflicting claims instead of silently overwriting them;
5. newly discovered anchors may alter the next retrieval query;
6. retrieval stops when confidence stabilizes or the call/character budget is exhausted.

`cogcoder/generation_retrieval.py` exposes `before_step` / `after_step` hooks. A future autoregressive decoder or host may invoke these hooks per token or per token block. **Current Nolane is not yet a conventional autoregressive text decoder with a measured per-token retrieval intervention**, so the accepted R2.1 evidence is cognition-step retrieval rather than a claim about token-level language-model performance.

`cogcoder/knowledge_adapters.py` can bridge live host search — web, files, vector databases or ordinary databases — into the same provenance-bound evidence contract. That adapter was added after FRESH and is utility code, not part of the locked KFIGG-21 performance claim.

## R2.0i active-causal evidence retained

R2.0i previously passed locked TRAIN -> DEV -> FRESH closed-loop admission without increasing neural parameters. On its consumed FIGG-18 FRESH split:

- frozen R2.0e baseline: **29/80 = 36.25%**
- R2.0i hybrid: **48/80 = 60.0%**
- gain: **+23.75 pp**
- causal prerequisites: **5% -> 100%**
- maximum family regression: **0**

That causal gain comes from a zero-parameter public active-experimentation controller around the neural stack, not from hidden simulator fields and not from new neural weights.

## Verification and scientific boundary

R2.1 keeps exact train/DEV/FRESH locks, source SHA binding, one-time FRESH consumption, matched retrieval budgets and explicit neural-vs-runtime attribution. `scripts/verify_r21_release.py` can replay all 200 consumed FRESH KFIGG-21 cases and verify the accepted aggregate result.

KFIGG-21 is synthetic and intentionally narrow. R2.1a does **not** prove general open-web question answering, scientific-literature mastery, coding-repository mastery, AGI, or superiority to >100B models. ARC-AGI-2, HLE/HLE-Verified, FrontierMath, Terminal-Bench and matched-budget reference-model runs remain separate external evaluation work.

The historical test tree is also not claimed universally green: some recovered R1.9/R2.0 research tests require old split checkpoint binaries that were intentionally removed from the one-weight release. Current R2.1 tests and release verification are separated from those historical fixtures.

## Key R2.1 files

- `cogcoder/knowledge_types.py` — immutable evidence/provenance contracts
- `cogcoder/knowledge_store.py` — deterministic zero-parameter hybrid retrieval
- `cogcoder/knowledge_ledger.py` — provenance verification, bounded working set, contradiction retention
- `cogcoder/retrieval_microcycle.py` — repeated uncertainty/query-drift-driven retrieval
- `cogcoder/generation_retrieval.py` — cognition/generation-step retrieval hook
- `cogcoder/knowledge_adapters.py` — host callback bridge for live external knowledge sources
- `cogcoder/r21_runtime.py` — behavior-preserving R2.0i + optional retrieval wrapper
- `cogcoder/kfigg21.py` — locked multi-hop retrieval mechanism benchmark
- `research/R2_1_CURRENT_BEST.json` — current accepted system state
- `research/R2_1_REALITY_REPORT.md` — exact claim boundary
- `scripts/verify_r21_release.py` — locked release verifier

## GitHub binary and Library boundary

GitHub `main` contains source, tests, locks, results, manifests, SHA-256 provenance and CI. The current conversational GitHub connector does not expose a practical local-binary/LFS/release-asset streaming path for the ~59.8MB `.pt`, so the repository does not pretend the raw weight bytes are present when they are not.

The milestone delivery also attempts persistent ChatGPT Library storage. If the Library backend rejects the artifact, that failure is reported explicitly rather than being represented as successful persistence.

## License

Research code currently follows licenses embedded in imported/derived components. A repository-wide license should only be declared after those component licenses are audited.
