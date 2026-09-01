# v0.0.12 RED checkpoint

Production code is intentionally unchanged at this checkpoint. The v0.0.12 contract requires:

- caller string evidence cannot create `ACTIVE + VERIFIED` memory;
- admission requires a clean subject-bound single-use `memory.verify` lease;
- stale/cross-memory admission leases fail closed;
- first-time forgetting requires a pre-issued exact-state `memory.forget` lease before archive;
- forget receipt/tombstone preserve the exact authority-use receipt and reject forged linkage on restore.

The next production commit must make these contracts GREEN without weakening v0.0.5–v0.0.11 invariants.
