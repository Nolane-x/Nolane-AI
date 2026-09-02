# Memory / Learning v0.0.14

Status: CLOSED / GREEN on `main`.

Scope was deliberately limited to the canonical public Family-B learning boundary:

- `nolane.memory.LearningSubstrate` and `nolane.memory.learning_substrate.LearningSubstrate` resolve to one governed public class identity;
- once a `SkillEvolutionEngine` is owned by a public `LearningSubstrate`, direct `substrate.skills.promote(...)` cannot bypass the substrate regression / causal promotion policy;
- `LearningSubstrate.from_state(...)` reconstructs through the public class and rebinds the exact shared skill engine to the same governor after restore;
- raw standalone `SkillEvolutionEngine` behavior remains compatible when no `LearningSubstrate` owns it;
- no second learning authority, lifecycle ledger, skill ledger, or evidence plane was introduced.

Implementation closure:

- the previous `learning_substrate.py` implementation was relocated byte-exact into private `_learning_substrate_impl.py`;
- `learning_substrate.py` is now the canonical thin governed boundary and forwards compatibility symbols to the private implementation;
- the promotion governor remains `LearningSubstrate`; evidence authority remains the shared `LearningEvidenceAuthority`;
- no `external.skills` component revision bump was taken because the standalone skill-engine semantics were intentionally preserved.

RED / GREEN evidence:

- first RED generation demonstrated the real public bypass on Python 3.11 and 3.13: the new contract failed because direct promotion did not raise, while 213 prior Memory contracts passed;
- second RED generation demonstrated the duplicate-class seam after the first facade attempt: the bypass contract passed, but the package/module class-identity contract failed while 214 prior contracts passed;
- final governed boundary plus restore contract passed the full Memory surface with 216/216 tests on Python 3.13 and the corresponding Python 3.11 matrix.

Integration / verification:

- exact verified B head `62d91104c5881f6646750c9f0ecf6626746255fc` was integrated with concurrent C11 latest-main `9940bd40d27b99686c1c169771ae70a086a527a9` as two-parent candidate `928b50bffb09605e680ca21b8da8af0b4967e236` with zero overlap in the four v0.0.14 files;
- PR #335 merge-ref acceptance passed Memory Learning Python 3.11/3.13, Refoundation Epoch 0 Python 3.11/3.13, E Acting Transactional Runtime Python 3.11/3.13, R1.9, and R2.0i;
- repository-wide historical frozen-release failures remained isolated to frozen source / release boundary sentinels; focused R2.62 behavior remained GREEN;
- PR #335 merged with exact-head protection as `d34c2f8c8dbac85d0ea4ee5ab46da873ee8c9eb0`, tree `44cf1af075f59e687e7f00d2db24a4b8baae5e64`;
- actual-main post-merge verification on that merge commit passed Memory Learning Substrate Python 3.11/3.13, R1.9, and R2.0i.

No proof-carrying Skill Forge expansion, dependency-revocation redesign, or cross-family redesign was part of v0.0.14.
