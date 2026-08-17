# R2.53 External Cognitive Reflex Runtime Design

## Goal
Externalize not only knowledge and memory but also a large class of **reasoning-control operators** so a compact model can be interrupted mid-cognition when its behavior is missing, wrong, stale, unverified, repetitive, poorly represented, or under-informed. The host runtime must be able to detect that deficit from machine-observable evidence, retrieve an appropriate procedural operator card, compile it only from trusted primitive operators, execute it, verify its effect, and return a compact state patch to the reasoner.

## Scientific boundary
R2.53 is a cognitive-runtime mechanism, not evidence of AGI. A synthetic reflex benchmark may establish that the mechanism works under controlled deficits; it cannot establish general metacognition, general tool use, or autonomous self-improvement on arbitrary real tasks. No AGI-readiness increase above the corrected R2.52 baseline may be justified by mechanism tests alone; large score changes require independent external transfer evidence.

## Starting point already present in Nolane
R2.1 already provides cognition-time knowledge retrieval (`CognitionTimeRetriever`, `GenerationRetrievalHook`), provenance-bound evidence, contradiction retention, and repeated retrieval after query drift. Other earlier releases contain epistemic workspaces, skill registries, active-debugging/VOI routing, counterexample-driven discovery, representation discovery, and operator synthesis. The missing piece is a unified **reflex control plane** that can recognize a cognitive deficit and route to external behavioral knowledge, not just factual knowledge.

## Core thesis
A reasoning operator is externalizable when its contract can be represented outside model weights as some combination of:

- trigger conditions,
- typed inputs and outputs,
- a bounded procedure over registered primitive operators,
- cost/risk/side-effect metadata,
- expected evidence or state changes,
- a verifier or falsifier,
- provenance/version information,
- credit and counterexample history.

Examples include retrieval, decomposition, branch search, backtracking, case splitting, counterexample generation, symbolic execution, representation switching, constraint propagation, temporal alignment, causal tracing, verification, tool discovery, and skill recall. Content-generating operators such as analogy or abduction may still require a model callback, but their invocation, contracts, budgets, routing, verification, and learning can remain external.

## Architecture

### 1. Cognitive signal plane
A `CognitiveSnapshot` is the observable state of an ongoing reasoning trajectory. It does not store private chain-of-thought. It stores safe structured telemetry only: objective, step index, self-confidence, progress score, unresolved requirements, evidence coverage, verifier failures, repeated action fingerprints, representation id, available capabilities, missing capabilities, stale/conflicting evidence, blocked subgoals, resource pressure, recent operators, and host observations.

`CognitiveDeficitDetector` converts telemetry into one or more `DeficitSignal`s with type, severity, confidence, evidence, and source. Important deficits include knowledge gap, episodic gap, working-memory pressure, planning gap, search stagnation, verification gap, representation mismatch, tool gap, skill gap, contradiction, uncertainty, information-acquisition gap, counterexample gap, credit ambiguity, routing uncertainty, temporal conflict, causal gap, mathematical support gap, code-analysis gap, metacognitive stagnation, goal ambiguity, constraint violation, resource pressure, novelty gap, and stopping uncertainty.

Crucially, objective evidence can override model self-confidence. A 0.99 self-confidence score cannot suppress a repeated-failure or verifier-failure signal.

### 2. External reasoning-operator registry
`CognitiveOperatorRegistry` stores primitive operators. Every operator has a stable id, family, semantic tags, preconditions, required/provided capabilities, deterministic cost/risk metadata, side-effect class, version/provenance, and an executor callback.

Operators are capability-safe: procedure retrieval never executes arbitrary retrieved source code. Retrieved procedures may only compose already registered primitive operator ids. Host-required operators are explicit and cannot silently pretend to be available.

### 3. Procedure cards: behavioral knowledge as retrievable memory
`ProcedureCard` is a provenance-bound external record describing **how to respond to a cognitive deficit**. It contains deficit tags, context tags, ordered primitive steps, preconditions, expected outputs, verifier requirements, cost ceiling, trust score, version, source uri, and content digest.

`ProcedureLibrary` supports retrieval by deficit/context and keeps multiple versions and alternatives. A card may encode patterns such as:

`knowledge_gap -> retrieve_knowledge -> integrate_evidence -> contradiction_check -> verify_claim`

or

`search_stagnation -> recall_counterexample -> diversify_search -> generate_discriminating_test -> re-rank -> verify_candidate`.

This is the direct generalization of R2.1 from **retrieving facts during thought** to **retrieving procedures/operators during thought**.

### 4. Safe procedure compiler
`ProcedureCompiler` validates that every step exists, its preconditions can be satisfied in order, the total cost/risk is within budget, the card provenance is valid, and a verifier is present when required. It emits a `CompiledProcedure`; no `eval`, `exec`, shell command, or arbitrary code from the card is permitted.

### 5. Reflex router and value-of-computation
`CognitiveReflexRouter` ranks compiled procedures using:

- deficit severity/confidence,
- semantic/context match,
- historical competence for this deficit,
- estimated information gain / expected progress,
- cost and risk,
- repetition/cooldown penalty,
- verifier availability,
- uncertainty about the procedure itself.

This is metareasoning: spend cognition only when expected value exceeds cost/risk.

### 6. External working state, episode memory, counterexample memory, and credit
The runtime stores structured external state rather than hidden model thoughts:

- `ExternalWorkingState`: evidence refs, hypotheses, subgoals, representation id, capability set, verified facts, unresolved requirements, compact notes.
- `EpisodeMemory`: prior objective/outcome/operator receipts with searchable tags.
- `CounterexampleMemory`: failed hypothesis/operator/context fingerprints and falsifying evidence.
- `CreditLedger`: beta-style success/failure statistics by procedure and deficit context, plus failure reasons and verifier receipts.

Successful procedure cards become easier to route in similar contexts; repeatedly failing cards are demoted or quarantined without changing model weights.

### 7. Cognitive reflex loop
The host loop is:

`reasoner step -> safe telemetry -> deficit detection -> procedure retrieval -> safe compilation -> route -> execute -> state patch -> verifier -> credit/counterexample update -> resume reasoner`.

If no trusted procedure fits, the runtime emits an explicit `acquire_behavioral_knowledge` request rather than inventing one. A host may satisfy it from documentation, a skill repository, a human, another agent, or operator synthesis. The base runtime fails closed when the missing behavior cannot be safely supplied.

## Externalization catalog
The catalog must cover the user's original 22 families and additional missing control functions. Every family contains multiple granular suboperators and labels each suboperator as `implemented`, `host_required`, or `knowledge_only` rather than pretending everything is executable.

Required original families:
1. factual knowledge
2. episodic memory
3. working memory
4. planning
5. search
6. verification
7. world model
8. tool knowledge
9. skill library
10. representation
11. uncertainty tracking
12. information acquisition
13. counterexample memory
14. credit assignment
15. self-improvement
16. attention/routing
17. multi-agent cognition
18. temporal reasoning
19. causal reasoning
20. mathematical reasoning support
21. code reasoning support
22. metacognition

Additional families that are separate enough to deserve explicit treatment:
23. goal/utility management
24. constraint/invariant management
25. resource/compute management
26. perception/observation normalization
27. action/execution control
28. communication/clarification
29. analogical transfer
30. abstraction/concept formation
31. hypothesis generation/abduction
32. counterfactual reasoning
33. consolidation/compression/forgetting
34. curiosity/novelty/exploration
35. identity/provenance/integrity
36. recovery/rollback/fault tolerance
37. stopping/termination
38. capability-boundary modeling

## Acceptance benchmark
R2.53 uses a frozen `External Cognitive Reflex` benchmark that does not test language fluency. It tests the mechanism under opaque task labels and distractor procedure cards.

Each heldout episode is a multi-stage state machine whose next deficit is revealed only by observable execution feedback. No single procedure card solves the whole episode. Episodes require 2-4 distinct behavioral interventions, such as knowledge retrieval followed by temporal conflict resolution and verification, or stagnation followed by counterexample recall and representation switch.

The benchmark compares:

- no-reflex baseline,
- self-confidence-only trigger,
- retrieve-procedure-once-at-start baseline,
- full interleaved external reflex runtime.

Acceptance requires:

- full runtime exact success on all frozen episodes,
- zero unsafe procedure execution,
- objective deficits detected even when self-confidence is adversarially high,
- procedure retrieval after the trajectory has already begun,
- at least one episode requiring a second different procedure because the first intervention exposes a new deficit,
- counterexample memory prevents repeating a previously falsified route,
- provenance verification passes,
- parent R2.52-R2.41 regression remains green,
- Python 3.11 and 3.13 focused determinism,
- Nolane World W5 audit retained as non-authoritative challenger; no fake convergence credit.

## Non-goals for R2.53
- No claim that every listed suboperator is already executable.
- No arbitrary execution of retrieved operator code.
- No private chain-of-thought storage.
- No claim of autonomous weight updates.
- No AGI claim from synthetic mechanism evidence.
- No large readiness-score increase without independent real-task transfer.
