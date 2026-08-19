from __future__ import annotations
import numpy as np


def test_r268_pinned_numpy_det_io_only_transfer() -> None:
    from research.r268_external_transfer import run_external_transfer
    result=run_external_transfer(np.linalg.det,source_id='numpy:numpy.linalg.det',source_version=np.__version__)
    assert result['passed'] is True
    assert result['source_exposure']=='io_only'
    assert result['source_id']=='numpy:numpy.linalg.det'
    assert result['discovery_validation_oracle_query_disjoint'] is True
    assert result['validation_oracle_query_attempts']==120
    assert result['validation_oracle_query_unique']==120
    assert result['validation_oracle_query_duplicates']==0
    assert result['selected_basis_size']==2
    assert result['globally_minimal'] is True
    assert result['false_accepts']==0
    assert result['terminal_exact']==result['terminal_cases']==6
    assert result['terminal_probe_exact']==result['terminal_probe_cases']==12
    assert result['oracle_accounting_exact'] is True
    assert result['oracle_calls_total']==result['source_calls_observed']
    assert result['trainable_parameter_count']==0


def test_r268_external_transfer_carries_complete_lower_basis_proof_ledger() -> None:
    from research.r268_external_transfer import run_external_transfer
    result=run_external_transfer(np.linalg.det,source_id='numpy:numpy.linalg.det',source_version=np.__version__)
    assert result['legal_interventions']==4
    assert result['semantic_profiles']==4
    assert result['lower_basis_count']==4
    assert result['lower_basis_certified']==4
    assert result['lower_basis_inconclusive']==0
    assert result['proof_ledger_complete'] is True
    assert len(result['lower_basis_universe_digest'])==64
    assert result['lower_basis_certificate_count']==4
    assert len(result['lower_basis_certificates'])==4
    assert all(row['basis_cardinality']==1 for row in result['lower_basis_certificates'])
    assert all(row['proof_kind']=='public_basis_target_collision' for row in result['lower_basis_certificates'])
    assert all(len(row['witness_digest'])==64 for row in result['lower_basis_certificates'])
    assert result['necessity_certificate_count']==2
    assert len(result['necessity_certificates'])==2
    assert all(row['proof_kind']=='public_target_collision' for row in result['necessity_certificates'])
