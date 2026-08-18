# R2.59 → R2.60 Evolution

R2.59 improves the efficiency of R2.58's bounded semantic-intervention search. R2.60 attacks a different bottleneck that remained in repository repair: after R2.52 enumerates executable multi-file patch hypotheses, sparse tests can leave several hypotheses behaviorally consistent, while the next diagnostic input is not selected for information gain.

R2.60 adds a zero-parameter active diagnostic layer over that existing finite repository-patch version space. Surviving candidates are executed on legal unlabeled probe inputs, their predicted outputs partition the version space, and a deterministic minimax rule selects the probe that minimizes worst-case residual ambiguity. Candidate IDs and candidate ordering are excluded from semantic ranking, target outputs are not read while probes are generated or ranked, and only the selected probe consumes an oracle label.

The authored six-episode R2.52 family keeps 75 patch candidates, 5–6 files, call depth 4–5 and only four initial tests. Passive initial evidence resolves 0/6; a target-independent one-probe baseline resolves 1/6; R2.60 resolves 6/6 with exactly one active selection label per episode, zero false terminal accepts, exact target macro sets, and candidate-ID/order invariance. A separate terminal verifier checks all 2,401 legal cases for each accepted episode.

A pinned external transfer uses callable I/O from NumPy 2.4.6 `numpy.gcd` without inspecting NumPy implementation source. Four host-authored executable hypotheses are deliberately consistent with the same two initial observations. The matched target-independent one-probe baseline remains ambiguous, while R2.60 selects one probe that splits all four hypotheses into singleton partitions, recovers the exact GCD behavior, and passes 625/625 terminal verification cases.

R2.60 was rebased onto the fully accepted R2.59 release rather than replacing it. Final hosted verification locks the R2.60 source blobs, checks the accepted R2.59 release manifest, recomputes authored and external evidence exactly, and reruns R2.59 through R2.41 protected lineage on the same tree.

The boundary remains strict. R2.60 consumes a host-supplied finite candidate version space and finite scalar probe domain. It does not independently generate missing repository hypotheses, invent arbitrary stateful/effectful tests, prove low total oracle cost, establish broad fresh-repository issue resolution, or imply AGI.
