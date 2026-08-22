import pytest

from cogcoder.organization.code_claims import ClaimMode, ClaimStatus, CodeClaimLedger


def test_disjoint_write_claims_coexist_and_paths_are_normalized():
    ledger = CodeClaimLedger()
    first = ledger.claim(
        agent_id='coding.backend.01',
        task_id='T-1',
        file_paths=('src\\api\\auth.py',),
        symbol_ids=('AuthService.refresh',),
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    second = ledger.claim(
        agent_id='coding.systems.01',
        task_id='T-2',
        file_paths=('src/runtime/loop.py',),
        symbol_ids=('RuntimeLoop.tick',),
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )

    assert first.file_paths == ('src/api/auth.py',)
    assert first.status is ClaimStatus.ACTIVE
    assert second.status is ClaimStatus.ACTIVE
    assert len(ledger.active_claims()) == 2


def test_overlapping_exclusive_claim_fails_atomically_for_path_or_symbol():
    ledger = CodeClaimLedger()
    ledger.claim(
        agent_id='coding.backend.01', task_id='T-1',
        file_paths=('src/api/auth.py',), symbol_ids=('AuthService.refresh',),
        mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    before = ledger.to_state()

    with pytest.raises(PermissionError):
        ledger.claim(
            agent_id='coding.systems.01', task_id='T-2',
            file_paths=('src/api/auth.py',), symbol_ids=(),
            mode=ClaimMode.EXCLUSIVE_WRITE,
        )
    assert ledger.to_state() == before

    with pytest.raises(PermissionError):
        ledger.claim(
            agent_id='coding.refactor.01', task_id='T-3',
            file_paths=('src/elsewhere.py',), symbol_ids=('AuthService.refresh',),
            mode=ClaimMode.EXCLUSIVE_WRITE,
        )
    assert ledger.to_state() == before


def test_release_preserves_history_and_removes_active_conflict():
    ledger = CodeClaimLedger()
    claim = ledger.claim(
        agent_id='coding.backend.01', task_id='T-1',
        file_paths=('src/api/auth.py',), mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    released = ledger.release(claim.claim_id, actor_agent_id='coding.backend.01')
    assert released.status is ClaimStatus.RELEASED
    assert ledger.get(claim.claim_id).status is ClaimStatus.RELEASED
    assert ledger.active_claims() == ()

    replacement = ledger.claim(
        agent_id='coding.systems.01', task_id='T-2',
        file_paths=('src/api/auth.py',), mode=ClaimMode.EXCLUSIVE_WRITE,
    )
    assert replacement.status is ClaimStatus.ACTIVE
    assert len(ledger.claims()) == 2
