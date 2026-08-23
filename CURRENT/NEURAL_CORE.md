# Neural Core

The current Neural composition is shared + regional + private.

`shared/neural-core/manifest.json` owns the shared core version, 56,000,000 physical parameters, and universal cognitive capability floor.

Each `regions/<region-id>/manifest.json` owns a regional Neural overlay version. Epoch 0 assigns zero separately-accounted physical parameters to this overlay; it is an explicit specialization/version layer, not a hidden new parameter allocation.

Each `ai/<agent-id>/profile.json` owns the identity's accepted neural version, private neural version, specialization version, and local physical parameter budget. Individual neural evolution therefore changes one profile without rewriting shared source.

No generated `RESOLVED.*` file is training/checkpoint authority. Frozen/checkpoint evidence remains governed by its existing evidence contracts.
