# R1.6 persistence status — 2026-08-12

## Authoritative crash recovery

A full live recovery ZIP has been created and integrity-tested locally:

- file: `Nolane-R1.6-LIVE-FULL-RECOVERY-2026-08-12.zip`
- size: ~3.1 GiB
- SHA-256: `870669d0179988d188a8547d1169373a65895955c6ba5b3aa85bf36b31f61c85`
- contents: the current R1.6 working tree plus all 60 local `.pt` checkpoints, excluding Python cache files
- `unzip -t`: no errors
- persisted to ChatGPT Library at `/Nolane/Nolane-R1.6-LIVE-FULL-RECOVERY-2026-08-12.zip`

## GitHub status

The connected GitHub interface can write UTF-8 files and Git blobs but does not expose a trustworthy local-file binary/LFS/release-asset upload path for multi-gigabyte model weights. Therefore this repository does **not** claim that all `.pt` bytes are stored on GitHub.

GitHub `main` stores:

- research source/protocol/result commits produced during R1.6;
- `research/R1_6_FULL_SNAPSHOT_MANIFEST.json`, which binds local checkpoints by SHA-256 and byte size;
- the live research ledger and per-experiment positive/negative results.

An attempted chunked binary source-snapshot transport was audited byte-for-byte and found unreliable through the connector display/transport layer. The non-authoritative chunk files were removed from `main` rather than leaving a silently corrupt recovery artifact.

## Rule going forward

Every completed research step is pushed to GitHub `main` immediately. Binary weights are protected by the Library recovery ZIP and checkpoint SHA manifests until a genuine Git LFS or release-asset uploader is available through the connected interface. Milestone completion still requires a complete delivery ZIP plus a Library copy.
