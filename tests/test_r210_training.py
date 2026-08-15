from pathlib import Path

import torch

from scripts.train_r210_copy_edit_proposer import (
    PARENT_EFFECTIVE_PARAMETERS,
    save_r210_bundle,
    save_r210_delta,
    train_copy_edit_proposer,
)


def test_small_training_produces_sub_300k_language_task_id_free_model():
    result = train_copy_edit_proposer(seed=210, epochs=2, rows_per_family=16, batch_size=16)
    assert result.proposer_parameters <= 300_000
    assert result.proposer_parameters > 0
    assert 0.0 <= result.train_accuracy <= 1.0
    assert all('language_embedding' not in key for key in result.proposer_state)
    assert all('task_embedding' not in key for key in result.proposer_state)


def test_bundle_appends_r210_delta_without_exceeding_80m(tmp_path: Path):
    parent = tmp_path / 'parent.pt'
    torch.save({'effective_parameters': PARENT_EFFECTIVE_PARAMETERS, 'version': 'parent'}, parent)
    result = train_copy_edit_proposer(seed=210, epochs=1, rows_per_family=8, batch_size=8)
    output = tmp_path / 'r210.pt'
    meta = save_r210_bundle(parent, output, result, lock_sha256='abc123')
    payload = torch.load(output, map_location='cpu', weights_only=True)
    assert payload['effective_parameters'] == PARENT_EFFECTIVE_PARAMETERS + result.proposer_parameters
    assert payload['effective_parameters'] < 80_000_000
    assert payload['r210_copy_edit_delta']['proposer_parameters'] == result.proposer_parameters
    assert meta['candidate_effective_parameters'] == payload['effective_parameters']


def test_small_delta_artifact_can_be_saved_without_full_parent(tmp_path: Path):
    result = train_copy_edit_proposer(seed=210, epochs=1, rows_per_family=8, batch_size=8)
    output = tmp_path / 'delta.pt'
    meta = save_r210_delta(output, result, lock_sha256='abc123')
    payload = torch.load(output, map_location='cpu', weights_only=True)
    assert payload['effective_parameters'] == PARENT_EFFECTIVE_PARAMETERS + result.proposer_parameters
    assert payload['r210_copy_edit_delta']['proposer_parameters'] == result.proposer_parameters
    assert meta['candidate_effective_parameters'] == payload['effective_parameters']
