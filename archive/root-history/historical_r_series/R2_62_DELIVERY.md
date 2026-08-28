# Nolane-AI R2.62 Delivery — Complementary Causal Experiment Program

Status: **ACCEPTED_BOUNDED_CAPABILITY**

R2.62 integrates an independently developed peer-AI capability without overwriting the accepted R2.60/R2.61 namespaces. The peer's already-green complementary experiment core is preserved byte-exact and ported into a clean R2.62 module on top of the accepted R2.61 release.

## Capability

R2.62 can search bounded pairs of pure-input interventions and a finite composition language when a target behavior cannot be recovered from either intervention alone. The search rejects pairs for which either singleton already solves the target, requires both interventions to contribute on validation data, and hierarchically synthesizes the two probe expressions under a matched local synthesis budget.

The accepted core is deterministic and adds **0 trainable parameters**.

## Hosted TDD

A real hosted RED preceded the R2.62 namespace implementation:

- run: `32124198258`
- job: `95671030685`
- head: `13409ab8900d78784873585f2880ea8596704179`
- failure: `ModuleNotFoundError: No module named 'cogcoder.r262_complementary_experiment_program'`

The production R2.62 module did not exist at that point. The peer core was then ported and the contract turned GREEN.

## Peer-AI integration

Peer source branch: `r260-complementary-experiment-program-gpt56sol`.

Peer head: `92e73ae4af5b060454141e057cda6033d4520a21`.

The old peer namespace was intentionally not merged because R2.60 was already accepted. The peer core blob `01e7953f42a858ac94052337b66834a30550d545` is reused exactly as `cogcoder/r262_complementary_experiment_program.py`, so the collaboration adds capability rather than overwriting another AI's milestone.

## Frozen authored evidence

`R2_62_PHASE_A_RESULT.json` is recomputed exactly in hosted CI:

- configurations: **3**
- discoveries: **3/3**
- matched flat-baseline failures: **3/3**
- full-program successes: **3/3**
- proper singleton-subset failures: **6/6**
- validation: **30/30 exact**
- challenge: **24/24 exact**
- rename/program-ID invariance: PASS
- argument permutation tracks positional roles: PASS
- matched synthesis budget respected: PASS
- flat baseline candidates: **30,000**
- hierarchical probe synthesis candidates: **14,136**
- wrong-pair false accepts: **0**
- selected composition operation: `add`
- trainable parameters added: **0**

## Pinned external transfer

Pinned source: `WarrenWeckesser/ufunclab@f1fbe6769850823a1976ccc28d14cd966130b645`, callable `ufunclab.deadzone`.

The learner receives callable I/O only; it does not parse the source implementation into the synthesis grammar. The function family was researcher-selected, so this is not blind external task discovery.

Exact hosted result:

- source exposure: `io_only`
- host-selected intervention: **false**
- derived anchors: `[-10.0, 10.0]`
- selected composition: `add`
- proper singleton-subset failures: **2/2**
- singleton challenge exactness: **4/8** and **6/8**; neither singleton solves the target
- full validation: **10/10**
- full challenge: **8/8**
- full heldout: **24/24**
- flat baseline: **FAIL** after 10,000 candidates
- hierarchical probe synthesis: **3,900** candidates total
- matched synthesis budget: PASS
- passing full programs: **1**
- total oracle calls: **172**
- trainable parameters added: **0**

External artifact from canonical run `32125347766`: `9320117536`.

## Canonical hosted verification

Canonical run: `32125347766`.

- R2.62 focused tests: **6/6**
- accepted/protected R2.61→R2.41 tests: **221/221**
- total relevant tests: **227/227**
- frozen source-lock check: PASS
- Phase-A recomputation: exact
- pinned external recomputation: exact
- Python 3.11 / 3.13 focused behavior: success / success

An earlier lineage run failed only during collection because NumPy was missing from that CI job. The dependency was corrected without changing the source-locked R2.62 production artifacts; the canonical run then passed the complete parent lineage.

## Nolane World 0.8.0

World `world_43c4537a8cd7` was used as an external audit/runtime around the integration. Its persisted session loads successfully through `WorldStore`, with SHA-256 `b71069ad77ff60013e84f9d9bf6e1322f56a38dbe10a2af4a79df3327807bce2`.

The W5 gate remains deliberately **FAIL**. Critical unknowns remain around blind distributional transfer, 3+ intervention scaling, effectful/stateful experiments, and learning the intervention/composition language itself. No convergence, challenger coverage, or active residency was fabricated.

## Readiness

Internal Coding-AGI engineering-readiness: **48.8/100**, delta **+0.3** from R2.61's 48.5.

The movement is intentionally small: R2.62 adds a real complementary multi-experiment structural capability and a distinct external deadzone transfer, but the language is still finite, pure-input, two-intervention, host-anchored and researcher-selected.

## Claim boundary

R2.62 demonstrates **bounded deterministic complementary two-intervention pure-input causal-program discovery, with singleton necessity, matched local synthesis budget, representation invariance, exact hosted lineage, and one pinned I/O-only external deadzone transfer**.

It does **not** establish open-ended experiment-language invention, learned anchors/composition operators, 3+ intervention scaling, stateful or effectful experiment design, blind external task discovery, broad repository coding autonomy, unrestricted program synthesis, AGI, or frontier-model equivalence.
