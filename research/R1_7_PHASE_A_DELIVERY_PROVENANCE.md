# R1.7 Phase A complete-delivery provenance

Date: 2026-08-12

Complete ZIP: `Nolane-R1.7-Phase-A-COMPLETE-DELIVERY-2026-08-12.zip`
- bytes: 282,008,044
- SHA-256: `2f02929527ff96fe9117bfb1a2285ef18a5b67d83544a3e8ab4ff9282cd5704f`
- `unzip -t`: No errors detected
- files in delivery manifest before manifest self-entry: 348

The archive contains the R1.7 Phase-A source/tests/scripts/results/docs plus actual binary weights for Stage-2, R1.2 ACE, R1.6 EffectProgress parent, and the accepted R1.7 CausalLaws checkpoint.

Because Library retrieval indexing is unreliable for a single ~269 MiB archive, the byte-identical ZIP is persisted as two Library volumes:
- `part-00`: 146,800,640 bytes, SHA-256 `99147013c6db7b3ae7f2e4cccc9e0240c65460989c2d917dcc9186f868ec2913`
- `part-01`: 135,207,404 bytes, SHA-256 `3eb7218d756e5cb6229189162624e1d98fcf64a8eb8fdbc1af3e97031723ac45`

Library path: `/Nolane/R1.7-Phase-A/`. The folder also contains `PHASE_A_VOLUMES_MANIFEST.json`, the original ZIP SHA file, and the full integrity-test log.

Reassembly:
`cat Nolane-R1.7-Phase-A-COMPLETE.part-* > Nolane-R1.7-Phase-A-COMPLETE-DELIVERY-2026-08-12.zip`
