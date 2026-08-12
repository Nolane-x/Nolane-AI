# Restore the full R1.6 no-weights source snapshot

The current GitHub connector cannot directly upload local binary `.pt` checkpoint files or Git LFS/release assets. To make the research tree crash-resistant anyway, the complete R1.6 working tree **excluding `.pt`, `.pyc`, and `__pycache__`** is stored as binary chunks under `snapshots/r1.6/no-weights/`.

Restore:

```bash
mkdir -p /tmp/r16-restore
cat snapshots/r1.6/no-weights/chunk-*.bin > /tmp/r16-restore/r16_full_noweights.tar.gz
sha256sum /tmp/r16-restore/r16_full_noweights.tar.gz
# expected: 37839189f18d3bcfad33620962f0615a2c2de39b7ba5f29f8a2a2f52918429d9
mkdir -p /tmp/r16-restore/tree
tar -xzf /tmp/r16-restore/r16_full_noweights.tar.gz -C /tmp/r16-restore/tree
```

`research/R1_6_FULL_SNAPSHOT_MANIFEST.json` records archive integrity plus SHA-256 and byte size for every local `.pt` checkpoint known at snapshot time. The checkpoint hashes are provenance records only; binary weights remain in the milestone ZIP/ChatGPT Library until a binary/LFS/release uploader is available to this connector.
