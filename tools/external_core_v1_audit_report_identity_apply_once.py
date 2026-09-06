from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "nolane/external_core/integration_admission_bundle.py"


def replace_once(old: str, new: str) -> None:
    text = TARGET.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one replacement target, found {count}: {old[:140]!r}")
    TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    '''@dataclass(frozen=True, slots=True)
class CanonicalAdmissionAuditReport:
''',
    '''def _exact_canonical_observation_digest(value: object) -> str:
    if type(value) is not str:
        raise ValueError("current observation audit observation digest must be an exact string")
    prefix = "canonical-observation-v1-"
    if not value.startswith(prefix):
        raise ValueError("current observation audit observation digest protocol identity mismatch")
    suffix = value[len(prefix) :]
    if len(suffix) != 64 or any(ch not in "0123456789abcdef" for ch in suffix):
        raise ValueError(
            "current observation audit observation digest must carry exactly 64 lowercase hexadecimal characters"
        )
    return value


@dataclass(frozen=True, slots=True)
class CanonicalAdmissionAuditReport:
''',
)

replace_once(
    '''        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))
        if current_observation:
            if observation_digest is not None and (
                type(observation_digest) is not str or not observation_digest.strip()
            ):
                raise ValueError("current observation audit observation digest must be an exact non-empty string")
            if not rows and observation_digest is None:
                raise ValueError("clean current observation audit requires an exact observation digest")
        protocol = ADMISSION_AUDIT_PROTOCOL if current_observation else HISTORICAL_ADMISSION_AUDIT_PROTOCOL
''',
    '''        rows = tuple(sorted(findings, key=lambda row: (row.code, row.subject_id, row.detail)))
        if type(current_observation) is not bool:
            raise ValueError("current_observation must be an exact boolean")
        if current_observation:
            if observation_digest is not None:
                observation_digest = _exact_canonical_observation_digest(observation_digest)
            if not rows and observation_digest is None:
                raise ValueError("clean current observation audit requires an exact observation digest")
        elif observation_digest is not None:
            raise ValueError("historical audit-v3 must not receive an observation digest witness")
        protocol = ADMISSION_AUDIT_PROTOCOL if current_observation else HISTORICAL_ADMISSION_AUDIT_PROTOCOL
''',
)

print("External Core v1 audit-report identity hardening applied with exact guards")
