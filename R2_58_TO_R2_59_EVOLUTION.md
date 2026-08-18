# R2.58 → R2.59 Evolution

R2.58 moved useful intervention choice inside the runtime for bounded pure-function subgoal discovery. Repository repair still had a parallel weakness: R2.52 could hold multiple executable patch hypotheses after sparse observations, but the next diagnostic input came from a pre-existing test sequence rather than being selected for information gain.

R2.59 adds an active diagnostic layer over the existing finite repository-patch version space. It executes surviving candidates on legal unlabeled probe inputs, partitions the candidate set by predicted behavior, and deterministically chooses the probe that minimizes worst-case residual ambiguity. Only the selected probe receives an oracle label; candidate identifiers and list order do not influence the ranking.

The authored frozen six-episode repository family preserves 75 candidate patches, 5–6 files, call depth 4–5 and only four initial observations. Passive initial evidence resolves 0/6 episodes. A target-independent one-probe baseline resolves 1/6. R2.59 resolves 6/6 with exactly one active selection query per episode, zero false terminal accepts and candidate-ID/order invariance. Probe generation does not read target outputs.

R2.59 then requires an independent terminal verification stage rather than accepting a singleton merely because active diagnosis selected it. That keeps the acceptance path fail-closed, but it also exposes an important scaling boundary: the current authored gate uses 2,401 verification oracle calls per episode. Therefore R2.59 proves selection-label efficiency, not lower total oracle cost.

A pinned external transfer against NumPy 2.4.6 `numpy.gcd` provides callable I/O only. Four host-authored executable hypotheses all agree on two initial observations. The active selector chooses one probe that splits them into four singleton partitions, recovers the exact GCD hypothesis and passes 625/625 independent verification cases; the matched target-independent one-probe baseline remains ambiguous. This is meaningful causal transfer of the diagnostic-selection mechanism, but it is not independent repository-candidate generation or general coding autonomy.

The boundary remains strict: R2.59 consumes an existing finite candidate version space and a finite host-provided probe domain. It does not invent arbitrary repository patches, stateful/effectful experiments, open-ended test domains, or AGI.
