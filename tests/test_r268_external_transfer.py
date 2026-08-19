from __future__ import annotations
import numpy as np

def test_r268_pinned_numpy_det_io_only_transfer() -> None:
    from research.r268_external_transfer import run_external_transfer
    result=run_external_transfer(np.linalg.det,source_id='numpy:numpy.linalg.det',source_version=np.__version__)
    assert result['passed'] is True
    assert result['source_exposure']=='io_only'
    assert result['source_id']=='numpy:numpy.linalg.det'
    assert result['selected_basis_size']==2
    assert result['globally_minimal'] is True
    assert result['false_accepts']==0
    assert result['terminal_exact']==result['terminal_cases']==6
    assert result['terminal_probe_exact']==result['terminal_probe_cases']==12
    assert result['oracle_accounting_exact'] is True
    assert result['oracle_calls_total']==result['source_calls_observed']
    assert result['trainable_parameter_count']==0
