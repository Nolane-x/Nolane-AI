from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "nolane/external_core/observation.py"

text = TARGET.read_text(encoding="utf-8")
old = '''def validate_observation_transition(
    previous: CanonicalObservationEnvelope | None,
    current: CanonicalObservationEnvelope,
    *,
    genesis: bool = False,
) -> tuple[ObservationFinding, ...]:
    current.validate_integrity()
'''
new = '''def validate_observation_transition(
    previous: CanonicalObservationEnvelope | None,
    current: CanonicalObservationEnvelope,
    *,
    genesis: bool = False,
) -> tuple[ObservationFinding, ...]:
    if type(genesis) is not bool:
        raise ValueError("genesis must be an exact boolean")
    current.validate_integrity()
'''
count = text.count(old)
if count != 1:
    raise RuntimeError(f"expected exactly one transition validator target, found {count}")
TARGET.write_text(text.replace(old, new, 1), encoding="utf-8")
print("External Core A10 exact-boolean genesis hardening applied")
