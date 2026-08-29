# Candidate Synthesis v0.0.1 Design

> `CURRENT/` remains canonical architecture authority. This document defines the bounded post-Epoch-0 feature design that will be implemented and then reflected into canonical architecture only after executable contracts are GREEN.

## Goal

Add one missing capability-generation boundary between existing evidence/causal/experimentation authorities and `external.capability_acquisition`, without reopening Refoundation migration work and without granting proposal generation any promotion, persistence, assurance, or neural authority.

## Component

`external.candidate_synthesis` v0.0.1 is a native, stateless proposal generator.

Control flow:

```text
Evidence / Causal / Experimentation / Cognitive Library
                         |
                         v
              Candidate Synthesis
                    proposals only
                         |
                         v
              CapabilityCandidate
                         |
                         v
             Capability Acquisition
                         |
                 CANDIDATE -> PROBATION
                         |
                     Assurance
                         |
                 PROMOTED / QUARANTINED
```

The implementation may own canonical source code for its own deterministic semantics, but it owns no persistent domain-state write authority. In particular it cannot mutate Cognitive Library, Capability Acquisition, Assurance, or the frozen neural asset.

## v0.0.1 vertical slice

The first real synthesis mode is `learned_abstraction_composition`.

Given two or more existing unary `LearnedAbstraction` source IDs from the canonical Cognitive Library, synthesis creates a new unary abstraction by ordered composition using canonical `AbstractionCall` nodes. Source order is semantic: `(A, B)` means `B(A(x))`; reordering may produce a different candidate.

The caller does not supply the candidate template. The candidate must be generated from canonical source abstractions, so this is proposal generation rather than candidate selection.

The synthesized abstraction is converted through the existing canonical `CapabilityCandidate.for_learned_abstraction` boundary. Synthesis never calls `CapabilityAcquisitionGovernor.admit`, `begin_probation`, `record_probation`, `promote`, or `quarantine`.

## Evidence separation

Generation evidence is explicitly phase-labelled. v0.0.1 accepts only `discovery` evidence during synthesis. `independent_challenge` and `final_assurance` evidence are rejected before candidate generation.

This preserves the three-stage separation:

```text
DISCOVERY EVIDENCE -> synthesis
INDEPENDENT CHALLENGE EVIDENCE -> probation
FINAL ASSURANCE EVIDENCE -> promotion
```

Experiment receipts and causal-program IDs are provenance references only; their presence does not grant authority.

## Determinism and receipts

Every request and receipt is immutable and canonicalized. A `SynthesisReceipt` binds at least:

- synthesis mode and objective,
- ordered source item IDs,
- normalized discovery evidence IDs,
- normalized experiment receipt IDs,
- normalized causal program IDs,
- generation budget,
- candidates considered,
- candidate ID when produced,
- semantic fingerprint when produced,
- explicit abstention reason otherwise.

`synthesis_id` is content-addressed from semantic request/result state. Reordering set-like provenance IDs does not change identity; reordering semantic source IDs does.

## Fail-closed rules

v0.0.1 must reject or abstain on:

- generation budget below one,
- fewer than two source abstractions,
- duplicate source IDs,
- missing source IDs,
- any non-unary source abstraction,
- non-discovery evidence supplied to generation,
- empty or duplicate provenance IDs,
- generated candidate already present in the Cognitive Library,
- generated candidate semantically equal to a source candidate,
- malformed/tampered request or receipt state.

Budget exhaustion is an abstention result, not a partial promotion signal.

## Mutation boundary

A synthesis call snapshots the library digest before generation and verifies it is unchanged before returning. The component stores no ledger. A produced candidate remains outside acquisition state until the caller explicitly invokes `CapabilityAcquisitionGovernor.admit(candidate)`.

## Deliberately out of scope

- executable operator invention,
- operator-family behavior synthesis,
- version-space mutation/search beyond the bounded composition slice,
- self-generated assurance,
- automatic probation or promotion,
- persistence or write-through to Cognitive Library,
- neural/checkpoint mutation,
- revival of historical `cogcoder` invention engines as runtime authority.

Historical R2.56/R2.61/R2.65 code is design provenance only.