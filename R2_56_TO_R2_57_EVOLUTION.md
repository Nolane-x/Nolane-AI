# R2.56 → R2.57 Evolution

R2.56 could invent a new pure behavior inside a fixed expression grammar. R2.57 adds a second learning timescale: verified solutions themselves become training material for the **language used by later synthesis**.

The main advance is not another hard-coded operator. The system finds repeated expression structure across distinct tasks, parameterizes it, scores whether reusing it compresses the corpus, and promotes useful abstractions into a content-addressed cognitive vocabulary. Subsequent synthesis can call these abstractions as primitives.

This required fixing a real search-architecture failure. Naive learned-call Cartesian enumeration caused a cheap abstraction to monopolize the candidate budget. R2.57 therefore adds fair scheduling and verified working-memory seed expansion, which lets a proven intermediate subgoal guide deeper composition before broad search resumes.

The frozen authored benchmark learns three reusable structural families and solves 6/6 compositions that the bounded R2.56 base solves 0/6. Clean hosted transfer to the independently sourced `ufunclab.linearstep` oracle also shows a causal difference under the frozen budget: the base fails while the grown vocabulary succeeds and verifies 24/24 heldout cases.

The boundary remains strict. The evaluator semantics and primitive operation basis are still host-designed. Vocabulary entries are structural abstractions over that basis, not arbitrary code or new effect semantics. The external harness also supplies a deliberate endpoint probe, so autonomous discovery of interventions/subgoals remains open.
