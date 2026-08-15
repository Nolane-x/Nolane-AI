# R2.14 Active Program Disambiguation — Design

## Purpose

R2.13 failed its frozen heldout because contextual skill routing selected the correct skill family while the inherited R2.3 synthesizer committed to the first shortest program that matched demonstrations. R2.14 addresses only that causal bottleneck: program underdetermination under sparse demonstrations.

## Scientific boundary

R2.14 is a zero-neural-parameter internal program-identification experiment. It does not claim unrestricted program synthesis, language understanding, AGI, or real-world coding generalization. It may only promote if a pre-registered heldout gate passes without post-hoc source or threshold changes.

## Architecture

### 1. Semantic version space

Represent each candidate by its complete output signature over a finite, predeclared probe domain. Programs with identical signatures are observationally equivalent on that domain and collapse into one equivalence class while preserving a deterministic representative path. Candidate construction explores all reachable signatures up to a hard depth/candidate/value budget rather than stopping at the first depth that fits demonstrations.

### 2. Demonstration filtering

Initial demonstrations remove all equivalence classes whose signature disagrees at observed inputs. Conflicting demonstrations are rejected. If no class remains, identification abstains instead of guessing.

### 3. Active discriminator selection

For each legal unobserved probe input, partition surviving equivalence classes by predicted output. Select the input minimizing the largest partition (minimax worst-case remainder); tie-break by greater expected elimination, then input value. This is deterministic and independent of candidate/program names.

### 4. Oracle update loop

Query an execution oracle only at the selected discriminator. Filter the version space by the observed output. Repeat under a hard oracle-call budget. Resolve when exactly one observational equivalence class remains. If multiple classes remain but no legal input distinguishes them, return an observational-equivalence certificate. If the budget expires with distinguishable classes remaining, abstain.

### 5. Evidence preservation

Every observation is appended to an immutable trace. The identifier never mutates prior demonstrations or rewrites the R2.13 negative result. A resolved skill can be promoted only with its initial demo digest, active-query trace, surviving semantic signature, and bounded-domain certificate.

## Benchmark

Four controlled program families exercise distinct ambiguity mechanisms rather than only XOR:

1. XOR-plus/additive compositions.
2. Affine arithmetic compositions.
3. Modular/conditional-like finite signatures using MOD plus arithmetic.
4. Mixed bitwise/arithmetic compositions.

Each task exposes sparse initial demonstrations intentionally chosen so at least two hypothesis classes may remain. DEV uses multiple deterministic seeds. Heldout uses disjoint seeds, target programs, constants, initial demonstration subsets, and query order perturbations.

## Baselines

- `shortest_consistent`: inherited R2.3 behavior under the same initial demos.
- `passive_fixed`: receives the same maximum number of oracle observations but at a fixed deterministic probe order.
- `random_budgeted`: deterministic seeded random probes under the same oracle budget.

## Pre-heldout acceptance gate

Freeze after DEV and before heldout. R2.14 is accepted only if all conditions hold:

- active heldout task accuracy >= 0.95;
- gain over shortest-consistent >= 0.25 absolute fraction;
- gain over passive-fixed >= 0.20;
- gain over random-budgeted >= 0.10;
- depth-3 stress accuracy >= 0.90;
- old-regime retention >= 0.95;
- ambiguous/out-of-class abstention = 1.00;
- program-identity permutation invariance = 1.00;
- false resolved accepts = 0;
- maximum active oracle calls <= 3;
- new neural parameters = 0;
- effective neural parameters remain 79,450,489.

A failure rejects R2.14 and leaves AGI engineering-readiness at 19.2/100.

## Testing

Unit tests cover semantic equivalence collapse, non-shortest hypothesis retention, minimax query selection, deterministic identity invariance, budget abstention, conflicting demonstrations, immutable evidence traces, and out-of-class behavior. Protocol tests verify source hashes and result/gate consistency.
