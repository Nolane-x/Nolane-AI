from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "nolane" / "external_core" / "integration_admission_bundle.py"
text = TARGET.read_text(encoding="utf-8")

replacements = (
    (
        'parser = argparse.ArgumentParser(description="Audit the canonical A7 atomic-observation admission bundle")',
        'parser = argparse.ArgumentParser(description="Audit the canonical A10 External Core v1 observation-bound admission surface")',
    ),
    (
        '    report = run_canonical_admission_audit(observed_epoch=args.observed_epoch)\n',
        '''    report = run_canonical_admission_audit(\n        observed_epoch=args.observed_epoch,\n        observation_genesis=True,\n        current_source_state_digests={},\n        current_evidence_digests={},\n        current_artifact_digests={},\n        current_freshness_fences={},\n        known_handoff_digests={},\n        current_work_trace_digests={},\n    )\n''',
    ),
)

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one CLI hardening target, found {count}: {old!r}")
    text = text.replace(old, new, 1)

TARGET.write_text(text, encoding="utf-8")
print("Canonical External Core A10 CLI hardening applied")
