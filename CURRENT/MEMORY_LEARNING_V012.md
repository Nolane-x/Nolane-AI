# Memory / Learning v0.0.12

Status: CLOSED / GREEN on `main`.

Scope was deliberately limited to two Family-B trust closures:

- verified memory admission consumes actual subject-bound learning evidence authority rather than caller-supplied evidence reference strings;
- first-time irreversible forgetting consumes a pre-issued exact-state-bound authority lease before archival/tombstoning begins.

Admission interaction closure preserves these derived invariants:

- compaction of VERIFIED sources creates a HYPOTHESIS / QUARANTINED candidate until the compacted memory earns its own independent verified admission;
- a replacement memory supersedes its incumbent only after the replacement crosses the explicit verified-admission boundary;
- restore validates persisted authority, lifecycle, compaction, and forgetting receipts fail-closed.

Integration / verification:

- clean Memory candidate `1285c0444ada59885a268ddfd2c411ff43ef4cad` passed Memory Python 3.11/3.13, Refoundation Epoch 0 Python 3.11/3.13, R1.9, and R2.0i;
- concurrent Family-D Goal/Design context hardening advanced `main` to `b38291098ca51131016d490bbc24cfee28cd6b7f`;
- the exact Family-D delta was unioned byte-for-byte into the Memory branch as two-parent integration commit `5a3cac6fb03c14f6476ef6ee2c71e492a84c9b2c`;
- final PR head `7e0290acc63ad9c1f030049d839e6af39191dc05` passed Memory Python 3.11/3.13, Refoundation Epoch 0 Python 3.11/3.13, R1.9, and R2.0i;
- PR #318 merged with exact-head guard as `5b2aa0add67e057011cce245ca00cd8ce7c35b77`;
- actual-main verification on that merge commit passed Memory Learning Substrate Python 3.11/3.13, R1.9, and R2.0i.

No Skill Forge expansion or cross-family redesign was part of v0.0.12.
