from __future__ import annotations

import json
from pathlib import Path

EXPECTED_PARAMETER_CEILING = 80_000_000


def verify_phase_a_lock(path: str | Path = 'research/R2_7_PRE_DEV_LOCK.json') -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    actual_ceiling = int(payload.get('phase_a_parameter_ceiling', -1))
    if actual_ceiling != EXPECTED_PARAMETER_CEILING:
        raise RuntimeError(
            f'R2.7 Phase-A parameter ceiling mismatch: {actual_ceiling} != {EXPECTED_PARAMETER_CEILING}'
        )
    acceptance = payload.get('acceptance')
    if not isinstance(acceptance, dict):
        raise RuntimeError('R2.7 lock is missing acceptance policy')
    if acceptance.get('external_coding_claim_allowed') is not False:
        raise RuntimeError('R2.7 lock must forbid external coding claims before external gates pass')
    return payload


if __name__ == '__main__':
    verify_phase_a_lock()
    print('R2.7 Phase-A lock verified')
