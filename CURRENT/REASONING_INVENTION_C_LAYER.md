# Reasoning / Invention C-Layer

## Status

This document defines the post-Epoch-0 architecture for the `C. Reasoning / Invention` capability family. It is intentionally additive: existing canonical authorities remain owners of their domain state, and this layer does not collapse them into a monolith.

The C-layer contains six independently governed authorities:

1. `external.cognitive_library` — reusable cognitive primitives and learned abstractions.
2. `external.candidate_synthesis` — stateless generation of capability proposals.
3. `external.capability_acquisition` — candidate/probation/promotion/quarantine lifecycle.
4. `external.causal` — bounded intervention and causal-program evidence.
5. `external.experimentation` — active probes, finite hypothesis spaces and verified shadow experiments.
6. `external.transfer_meta` — verified portable experience and governed cross-domain reuse.

The missing architectural element is not another owner of those states. It is a typed protocol spine that makes their outputs composable without transferring authority.

## Design objective

Turn the six C authorities into a closed, evidence-driven invention cycle:

```text
Cognitive Library / Epistemic observations
                |
                v
      Capability-gap / problem framing
                |
                v
        Candidate Synthesis
             proposals
                |
                v
        Invention Hypotheses
  anchors + assumptions + invariants
                |
        +-------+-------+
        |               |
        v               v
      Causal       Experiment Design
     challenge     controls / ablations
        |               |
        +-------+-------+
                v
       Independent challenge
       VERIFIED / FALSIFIED /
       INCONCLUSIVE / ABSTAIN
                |
          +-----+-----+
          |           |
          v           v
   Capability Gap   Transfer Intent
          |           |
          v           v
   explicit caller   explicit caller
   Acquisition       Transfer/Meta
          |           |
          +-----+-----+
                v
             Assurance
                |
                v
  promoted/reusable authority only here
```

No arrow in this diagram implies automatic mutation. Every transition across an authority boundary is represented by immutable, content-addressed evidence or intent.

## Nolane World synthesis

The design adapts the strongest mechanisms from Nolane World 0.12.0 into Nolane AI runtime contracts rather than copying World modules directly:

- **Evidence-bounded invention.** Every hypothesis carries explicit anchor evidence. Unproven premises are assumptions, not silently promoted facts.
- **Falsifiability before promotion.** A hypothesis must carry an executable verification plan before it can be treated as a challenge-ready object.
- **Generalized variables and invariants.** Transfer claims name the invariant structure expected to survive a domain shift rather than copying surface details.
- **Negative controls and ablations.** Verification design makes counterfactual failure conditions explicit.
- **Information efficiency.** Experiment designs expose expected information gain and cost separately; they do not hide them inside an unverifiable optimizer claim.
- **Pareto reasoning.** Invention candidates are compared across benefit, evidence quality, robustness, transferability, uncertainty, complexity and verification cost. The core protocol keeps the non-dominated frontier rather than pretending one universal scalar objective exists.
- **Deterministic convergence.** Set-like evidence/provenance is canonicalized, semantic ordering remains explicit, IDs are content-addressed and restore must reject tampering.
- **Separation of hypothesis from generalized knowledge.** A generated or challenged hypothesis never becomes Cognitive Library authority merely because it scored well.
- **Rollback-friendly self-improvement.** Capability Acquisition and Transfer/Meta remain the only C-layer lifecycle governors able to cross their existing retrieval/reuse firewalls, with Assurance still external and exact.

## Authority invariants

### I1 — Proposal is not authority

Candidate Synthesis may create a `CapabilityCandidate`; it cannot admit, probation, promote, quarantine, persist or install that candidate.

### I2 — Hypothesis is not knowledge

The Reasoning/Invention protocol may describe, rank and challenge hypotheses. It cannot register an abstraction/family in Cognitive Library.

### I3 — Experiment is not Assurance

An Experimentation receipt is evidence about a finite behavioral hypothesis. It cannot self-promote a capability and cannot mint a final Assurance receipt.

### I4 — Causal support is bounded support

A Causal program ID may strengthen provenance or transfer support, but it does not by itself prove a general causal law outside the exact accepted causal ledger row.

### I5 — Acquisition is explicit

A capability gap or invention receipt can nominate a candidate for downstream acquisition. Only an explicit caller action against `CapabilityAcquisitionGovernor` creates lifecycle state.

### I6 — Transfer is explicit and destination-bound

A transfer intent must name source and target domains, generalized variables, invariants, assumptions and transfer trials. Existing `external.transfer_meta` remains the reuse authority and existing Assurance remains the acceptance authority.

### I7 — No self-verification loops

Discovery evidence may frame and synthesize. Independent-challenge evidence may falsify or support. Final-Assurance evidence is owned downstream. The same phase cannot mint its own stronger authority.

## Native protocol objects

The first implementation slice introduces `nolane.external_core.reasoning_invention` as a stateless protocol module.

### `ReasoningEvidenceRef`

A normalized reference to evidence already owned elsewhere:

- `evidence_id`
- `phase`: discovery, independent challenge, final assurance
- `source_component`
- `witness_id`

Human labels are excluded from semantic identity.

### `VerificationPlan`

An immutable falsification contract:

- metric and baseline IDs
- success threshold
- one-variable perturbation/probe IDs
- negative-control IDs
- ablation IDs
- stop-condition IDs
- hard maximum verification cost
- expected information gain

`information_efficiency` is a transparent derived value (`expected_information_gain / max_cost`) used only descriptively. It never grants promotion authority.

### `InventionHypothesis`

A content-addressed hypothesis with:

- falsifiable statement
- discovery evidence anchors
- explicit assumptions
- generalized variables
- invariants
- predicted metric deltas
- exact `VerificationPlan`
- optional Candidate Synthesis proposal ID

Only discovery-phase evidence may anchor generation. Challenge/final evidence enters through a separate verdict object.

### `InventionAssessment`

A bounded multi-objective assessment vector:

- evidence alignment
- anomaly/counterexample coverage
- expected gain
- robustness
- transferability
- uncertainty
- complexity
- verification cost

All dimensions are explicit. Core comparison exposes Pareto dominance. No hidden scalar weighting is canonical.

### `InventionCandidate`

Binds one hypothesis and assessment with optional causal-program and experiment-receipt provenance. Causal/experiment IDs remain references, not lifecycle authority.

### `HypothesisChallenge`

An immutable independent-challenge result. It binds:

- target hypothesis ID
- challenge evidence IDs
- causal program IDs
- experiment receipt IDs
- verdict: verified, falsified, inconclusive, or abstain
- reason

Only independent-challenge evidence is legal here. A VERIFIED challenge requires at least one causal or experiment receipt reference; an evidence-only label cannot silently create verification authority.

### `CapabilityGap`

A proof-shaped request for downstream acquisition:

- objective
- capability kind
- exact Cognitive Library baseline digest
- evidence showing insufficiency
- acceptance-test IDs
- nominated Candidate Synthesis candidate ID
- optional verified challenge ID

This object cannot call the acquisition governor. It is an intent and provenance envelope only.

### `TransferIntent`

A destination-bound proposal for transfer/meta reuse:

- source and target domains
- verified challenge/source receipt IDs
- generalized variables
- invariants
- target assumptions
- transfer-trial IDs

Source and destination must differ. The intent cannot accept reuse or mint Assurance.

### `ReasoningInventionReceipt`

A canonical aggregation receipt over one reasoning pass. It can bind hypotheses, Pareto-frontier candidate IDs, challenge IDs, capability-gap IDs and transfer-intent IDs. It stores no mutable authority and has no promoted/installed/reused flag.

## Multi-objective frontier

For two assessment vectors `A` and `B`, `A` dominates `B` only when:

- A is no worse on every maximize dimension: evidence alignment, anomaly coverage, expected gain, robustness, transferability;
- A is no worse on every minimize dimension: uncertainty, complexity, verification cost;
- and A is strictly better on at least one dimension.

The protocol returns all non-dominated candidates sorted by canonical candidate identity. This preserves legitimate trade-offs instead of encoding an arbitrary global utility function into architecture.

## Fail-closed behavior

The protocol rejects:

- empty semantic IDs;
- duplicate set-like evidence/provenance references;
- non-finite numeric fields;
- scores outside `[0, 1]` where bounded scores are required;
- verification plans without a negative control, ablation or stop condition;
- zero/non-positive verification cost;
- challenge/final evidence used as discovery anchors;
- discovery/final evidence used as independent challenge authority;
- VERIFIED verdicts with no causal/experiment support;
- capability gaps without insufficiency evidence or acceptance tests;
- transfer intents where source equals target;
- transfer intents without an invariant or transfer trial;
- non-canonical serialized state or tampered content-derived IDs.

## Cross-component integration contract

The protocol consumes stable IDs and immutable snapshots, not mutable authority objects. This deliberately minimizes coupling while A/B and other Nolane AI regions evolve in parallel.

- Cognitive Library is read through its exact `digest` and reusable item IDs.
- Candidate Synthesis is referenced through proposal/candidate IDs.
- Causal is referenced through accepted causal-program IDs.
- Experimentation is referenced through shadow/ledger receipt IDs.
- Capability Acquisition receives a caller-selected `CapabilityGap`/candidate later; there is no write-through API here.
- Transfer/Meta receives a caller-selected `TransferIntent` later; there is no reuse acceptance API here.
- Assurance remains downstream and unchanged.

## Evolution roadmap

### C1 — Protocol spine (this slice)

Implement the immutable reasoning/invention protocol, Pareto frontier, challenge separation, capability-gap and transfer-intent envelopes with canonical round-trip/tamper rejection.

### C2 — Experimentation v0.0.2

Add explicit experiment design artifacts over the existing finite version-space engine: cost/information metadata, negative controls, ablations, stop policies and plan-to-shadow-receipt binding. Existing R2.60 selection remains backward compatible.

### C3 — Causal v0.0.2

Add explicit causal-hypothesis challenge envelopes and proper-subset/ablation evidence bindings without claiming general causal discovery. Keep current bounded intervention program semantics intact.

### C4 — Capability Acquisition v0.0.2

Upgrade probation from four loose summary fields to typed probation trials: environment/holdout identity, independent verifier evidence, causal/experimental challenge receipts, reliability calibration and exact gap/candidate binding. Preserve the current Assurance-gated promotion firewall.

### C5 — Cognitive Library v0.0.2

Add read-only fit/coverage diagnostics and provenance-backed capability descriptors so a capability gap can be demonstrated against an exact library baseline without turning retrieval heuristics into write authority.

### C6 — Transfer/Meta v0.0.2

Bind transfer reuse to generalized-variable/invariant envelopes and destination trial matrices; record negative transfer by target regime; retain exact Assurance authorization and revocation semantics.

### C7 — Closed-loop evaluation

Evaluate end-to-end invention cycles under fixed budgets: discovery evidence -> synthesis -> challenge -> experiment -> acquisition/transfer intent. Measure false acceptance, abstention quality, information efficiency, generalization, robustness and regression count. Claims remain bounded to reproduced evidence.

## Non-goals

This architecture does not claim AGI, unrestricted autonomous science, arbitrary code invention, unlimited causal discovery, unrestricted self-modification or automatic capability promotion. It establishes a stronger engineering substrate in which such future capabilities, if implemented, must remain falsifiable, attributable, bounded and reversible.