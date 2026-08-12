# R1.6 Full Weight Recovery Volumes

Persisted on 2026-08-12 (Asia/Bangkok).

The connected GitHub interface does not expose Git LFS, release-asset upload, or local binary-file upload, so the multi-gigabyte `.pt` lineage cannot be physically pushed through this connector without corrupt/unsafe text encoding. The complete recovery package is therefore persisted byte-for-byte in the ChatGPT Library as 18 ordered binary volumes under `/Nolane/R1.6-Recovery/`.

## Original package

- `Nolane-R1.6-LIVE-FULL-RECOVERY-2026-08-12.zip`
- bytes: `3336385126`
- SHA-256: `a6f086d997d402ca1e720dff57e7d23b42132d2c3bd4179daec4e80637b055a9`

## Volumes

- `Nolane-R1.6-FULL.part-00` through `Nolane-R1.6-FULL.part-17`
- parts 00–16: 180 MiB each
- part 17: 127,742,566 bytes
- exact per-part SHA-256 values are stored in `RECOVERY_VOLUMES_MANIFEST.json` in the same Library folder.

Restore on Linux/macOS:

```bash
cat Nolane-R1.6-FULL.part-* > Nolane-R1.6-LIVE-FULL-RECOVERY-2026-08-12.zip
sha256sum Nolane-R1.6-LIVE-FULL-RECOVERY-2026-08-12.zip
```

The resulting SHA-256 MUST equal `a6f086d997d402ca1e720dff57e7d23b42132d2c3bd4179daec4e80637b055a9` before use.

GitHub remains the crash-resistant source/protocol/result ledger. Binary weight recovery is provenance-bound by this document plus `research/R1_6_FULL_SNAPSHOT_MANIFEST.json` and the Library volume manifest.