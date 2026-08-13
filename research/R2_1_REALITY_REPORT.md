# Nolane R2.1a Reality Report — Cognition-Time Retrieval Fabric

## Accepted result
R2.1a keeps the accepted R2.0i neural system frozen at **78,779,253 effective parameters** and adds **0 neural parameters**. It adds a runtime retrieval fabric that can retrieve between cognition/generation steps, keep an append-only provenance ledger, retain contradictions, and issue a new retrieval query after newly retrieved evidence changes the active knowledge state.

KFIGG-21 uses a matched maximum evidence budget: retrieve-once gets one query with up to 4 chunks; interleaved retrieval gets up to four queries with one chunk each. Both therefore consume at most 4 chunks. The interleaved solver derives every next query only from the original question and chunks it has actually retrieved.

| Split | Retrieve once | Interleaved | Gain |
|---|---:|---:|---:|
| Train gate, 200 cases | 68.0% | **100%** | **+32.0 pp** |
| DEV, 200 cases | 66.5% | **100%** | **+33.5 pp** |
| FRESH 2000..2199, 200 cases | 67.0% | **100%** | **+33.0 pp** |

FRESH provenance failures: **0**. Median retrieved characters among solved examples are 108 for retrieve-once and 81 for interleaved, ratio **0.75**. The FRESH split is consumed and R2.1a core is frozen.

Descriptively, FRESH contained 71 two-hop, 63 three-hop, and 66 four-hop cases. Retrieve-once solved all two/three-hop cases but 0/66 four-hop cases under the same four-chunk budget. Interleaved solved all 200/200. This is the intended mechanism test: later hops cannot be targeted until an intermediate entity has been retrieved.

## What changed
- `knowledge_types.py`: immutable document/chunk provenance contracts.
- `knowledge_store.py`: deterministic zero-param lexical + character-ngram hybrid retrieval and composite source fusion.
- `knowledge_ledger.py`: tamper detection, dedupe, bounded working sets, contradiction retention.
- `retrieval_microcycle.py`: uncertainty/query-drift trigger, repeated retrieval, anchor-based re-query, call/character budgets.
- `generation_retrieval.py`: generic `before_step`/`after_step` hook. A future token decoder may call it per token or per block; current Nolane can call it between cognitive steps.
- `r21_runtime.py`: opt-in wrapper. With no knowledge source, it calls accepted R2.0i directly and reproduces its behavior.
- `knowledge_adapters.py`: post-FRESH host utility for bridging live web/files/vector-DB/database callbacks into the evidence contract. It is **not** part of the FRESH performance claim.

## Scientific boundary
This is not evidence that the 78.8M neural weight internally knows more world facts. It demonstrates the opposite design thesis: a compact neural system can be paired with external memory and retrieve knowledge dynamically rather than storing all knowledge in parameters.

KFIGG-21 is synthetic and intentionally isolates multi-hop retrieval mechanics. It does not establish performance on open-domain QA, current web search, scientific literature review, coding repositories, ARC-AGI-2, HLE, FrontierMath, Terminal-Bench, or any >100B comparison. Those need separate matched-budget external runs.

Current Nolane is also not yet a conventional autoregressive text decoder with a proven per-token retrieval intervention. R2.1 exposes a generation-step hook that *can* be called at token granularity by a future decoder/host, but the accepted evidence is cognition-step retrieval on KFIGG-21.
