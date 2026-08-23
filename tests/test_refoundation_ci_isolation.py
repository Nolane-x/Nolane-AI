from __future__ import annotations

from pathlib import Path


LEGACY_DUPLICATE_GATES = (
    ".github/workflows/coding-agi-assurance-part8.yml",
    ".github/workflows/coding-agi-coding-part5.yml",
    ".github/workflows/coding-agi-multi-agent-coordination-part13.yml",
    ".github/workflows/coding-agi-foundation.yml",
    ".github/workflows/r19-integrity.yml",
    ".github/workflows/coding-agi-research-part10.yml",
    ".github/workflows/coding-agi-debugging-part6.yml",
    ".github/workflows/coding-agi-ephemeral-foundry-part14.yml",
    ".github/workflows/coding-agi-ui-part7.yml",
    ".github/workflows/coding-agi-architecture-integration-part4.yml",
    ".github/workflows/coding-agi-requirements-planning-part3.yml",
    ".github/workflows/coding-agi-evaluation-campaign.yml",
    ".github/workflows/coding-agi-operations-part9.yml",
    ".github/workflows/coding-agi-evaluation-scaling-part15.yml",
    ".github/workflows/r20i-integrity.yml",
    ".github/workflows/coding-agi-memory-context-part11.yml",
    ".github/workflows/coding-agi-individual-evolution-part12.yml",
)

MARKER = "REF0-CI-ISOLATION"
HEAD_GUARD = "github.event_name != 'pull_request' || !startsWith(github.head_ref, 'refoundation/')"


def test_observed_legacy_duplicate_gates_skip_refoundation_pull_requests() -> None:
    for relative_path in LEGACY_DUPLICATE_GATES:
        text = Path(relative_path).read_text(encoding="utf-8")
        assert MARKER in text, relative_path
        assert HEAD_GUARD in text, relative_path


def test_refoundation_gate_itself_is_never_suppressed_by_legacy_isolation() -> None:
    text = Path(".github/workflows/refoundation-epoch0-wave1.yml").read_text(encoding="utf-8")
    assert MARKER not in text
    assert HEAD_GUARD not in text
