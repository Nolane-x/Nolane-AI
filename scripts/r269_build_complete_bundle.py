from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

LOCK = Path('R2_69_PRE_HOSTED_LOCK.json')
OUT = Path('release/Nolane-AI-R2.69-COMPLETE.zip')
SHA = Path('release/Nolane-AI-R2.69-COMPLETE.zip.sha256')
PREFIX = 'Nolane-AI-R2.69/'
REQUIRED = {
    'R2_69_PRE_HOSTED_LOCK.json',
    'R2_69_PHASE_A_RESULT.json',
    'R2_69_EXTERNAL_TRANSFER.json',
    'R2_69_PROMOTION_AUTHORITY.json',
    'R2_69_WORLD_BOUNDED_ADJUDICATION.json',
    'cogcoder/r269_scoped_promotion.py',
    'cogcoder/r269_promotion_authority.py',
    'cogcoder/r269_governed_runtime.py',
    'benchmarks/kfigg/r269_promotion_authority.py',
    '.github/workflows/r269-promotion-authority.yml',
}


def _git_blob(path: str) -> str:
    return subprocess.check_output(['git', 'hash-object', path], text=True).strip()


def _tracked_files() -> tuple[str, ...]:
    raw = subprocess.check_output(['git', 'ls-files', '-z'])
    return tuple(sorted(row.decode() for row in raw.split(b'\0') if row))


def verify_lock() -> dict[str, object]:
    if not LOCK.is_file():
        raise RuntimeError('R2.69 source is not frozen')
    lock = json.loads(LOCK.read_text())
    if lock.get('schema_version', 0) < 3:
        raise RuntimeError('R2.69 lock predates hosted promotion authority')
    if lock.get('milestone') != 'R2.69' or lock.get('status') != 'PRE_HOSTED_SOURCE_AND_EVIDENCE_LOCK':
        raise RuntimeError('invalid R2.69 lock state')
    if lock.get('writers_retired') is not True:
        raise RuntimeError('release writers are not retired')
    if lock.get('w5_convergence_claimed') is not False:
        raise RuntimeError('W5 convergence must not be claimed')
    if lock.get('added_trainable_parameters') != 0:
        raise RuntimeError('R2.69 release layer must add zero trainable parameters')
    if lock.get('host_attested_promotion_authority_required') is not True:
        raise RuntimeError('host-attested promotion authority is required')
    if lock.get('promotion_authority_source_frozen') is not True:
        raise RuntimeError('promotion authority source must be frozen')
    if lock.get('exact_rollback_registry_required') is not True:
        raise RuntimeError('exact rollback registry authority is required')
    if lock.get('promotion_gate_pass') is not True:
        raise RuntimeError('promotion authority gate is not accepted')
    for field in (
        'promotion_semantic_digest',
        'promotion_authority_root_digest',
        'promotion_hosted_attestation_digest',
        'promotion_authority_envelope_digest',
        'promotion_verifier_workflow_blob',
    ):
        if not str(lock.get(field, '')).strip():
            raise RuntimeError(f'missing promotion lock field: {field}')
    blobs = lock.get('frozen_git_blobs')
    if not isinstance(blobs, dict) or not blobs:
        raise RuntimeError('frozen_git_blobs missing')
    for path, expected in sorted(blobs.items()):
        if not Path(path).is_file() or _git_blob(path) != expected:
            raise RuntimeError(f'frozen blob mismatch: {path}')
    promotion = json.loads(Path('R2_69_PROMOTION_AUTHORITY.json').read_text())
    if promotion.get('promotion_gate_pass') is not True:
        raise RuntimeError('promotion authority receipt is not accepted')
    if promotion.get('semantic_result_digest') != lock.get('promotion_semantic_digest'):
        raise RuntimeError('promotion semantic digest does not match lock')
    if promotion.get('authority_root_digest') != lock.get('promotion_authority_root_digest'):
        raise RuntimeError('promotion authority root does not match lock')
    if promotion.get('hosted_attestation_digest') != lock.get('promotion_hosted_attestation_digest'):
        raise RuntimeError('promotion hosted attestation does not match lock')
    if promotion.get('authority_envelope_digest') != lock.get('promotion_authority_envelope_digest'):
        raise RuntimeError('promotion authority envelope does not match lock')
    if promotion.get('verifier_workflow_blob') != lock.get('promotion_verifier_workflow_blob'):
        raise RuntimeError('promotion verifier workflow blob does not match lock')
    return lock


def build() -> tuple[str, int]:
    verify_lock()
    for path in REQUIRED:
        if not Path(path).is_file():
            raise RuntimeError(f'missing required release file: {path}')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    files = tuple(path for path in _tracked_files() if Path(path).is_file())
    with zipfile.ZipFile(OUT, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(PREFIX + path, date_time=(2026, 8, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, Path(path).read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(OUT) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('zip integrity check failed')
        names = set(archive.namelist())
        missing = {PREFIX + path for path in REQUIRED} - names
        if missing:
            raise RuntimeError(f'release zip missing files: {sorted(missing)}')
    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()
    SHA.write_text(f'{digest}  {OUT.name}\n')
    return digest, OUT.stat().st_size


if __name__ == '__main__':
    digest, size = build()
    print(f'R269_COMPLETE_ZIP_SHA256={digest}')
    print(f'R269_COMPLETE_ZIP_BYTES={size}')
