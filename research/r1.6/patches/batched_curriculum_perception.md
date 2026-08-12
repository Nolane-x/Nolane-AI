# R1.6 Batched Stage-2 Curriculum Perception

Date: 2026-08-12 (Asia/Bangkok)

## Purpose

Procedural-breadth experiments were timing out largely because the frozen ~50M Stage-2 trunk encoded every current and next observation one-by-one. This change does **not** alter the representation or benchmark. It batches and deduplicates the frozen text->latent transform so more independent train worlds can be used per optimizer budget.

## Verified behavior

New API:

```python
class FrozenStage2ObservationEncoder:
    def encode_texts(self, texts: Sequence[str], *, batch_size: int = 32) -> Tensor:
        rows = [str(text) for text in texts]
        if not rows:
            return torch.empty((0, self.trunk.d_model), dtype=torch.float32)
        size = int(batch_size)
        if size < 1:
            raise ValueError("batch_size must be positive")
        outputs: list[Tensor] = []
        with torch.inference_mode():
            for start in range(0, len(rows), size):
                ids = torch.stack([
                    self.tokenizer.encode_balanced(text, max_length=self.max_length)
                    for text in rows[start : start + size]
                ])
                output = self.trunk(ids, recurrent_steps=self.recurrent_steps)
                outputs.append(output["latent_state"].detach().cpu())
        return torch.cat(outputs, dim=0).clone()
```

A new `collect_teacher_trajectories_batched(...)` performs the exact same sequential oracle/world simulation as the legacy collector, records public current/next observation strings plus counterfactual targets, deduplicates observation texts, calls `encode_texts`, and reconstructs the same `TeacherTrajectory` / `TeacherStep` objects.

## RED -> GREEN tests

Two tests were added before implementation:

1. `test_batched_stage2_encoding_matches_sequential_encoding`
   - compares three heterogeneous observation strings.
   - requires `torch.allclose(..., atol=1e-6, rtol=1e-6)` against sequential Stage-2 encoding.
2. `test_batched_teacher_collection_matches_sequential_teacher_targets`
   - compares one task per family.
   - verifies task IDs, family, step count, action label, public observation, current latent, next latent and counterfactual failure tensors.

RED failure was caused by missing `encode_texts` and missing `collect_teacher_trajectories_batched`; after implementation both tests pass.

## Performance measurement

Same Stage-2 checkpoint, train split, 5 tasks per family (15 total), 107 teacher transitions:

- Sequential collection: **4.339 s**
- Batched collection (`batch_size=32`): **1.848 s**
- Speedup: **2.35x**

No fresh task was opened.

## Source integrity after change

- `cogcoder/neural_system2_curriculum.py` SHA-256: `db0e845d7b41f650d5851de01b183fe4a04a197e2640fb5bc2ebc44f9b64a635`
- `tests/test_neural_system2_curriculum.py` SHA-256: `67edef186edb1f055fab17815a6ab7455f7c94657c41ce19143696f0e507b821`

This optimization is retained because it changes compute efficiency while preserving the learned representation and teacher targets.
