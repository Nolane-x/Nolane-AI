from __future__ import annotations

import hashlib
from pathlib import Path


TARGET = Path('cogcoder/r267_three_probe_causal_composition.py')
BEFORE_BLOB = '6ff70969be3404c58ddd43c785b5d0450ee32bd1'
AFTER_BLOB = 'ee7dc56db206a1e2f8a9da47976db112870dcd3e'


def git_blob_sha(text: str) -> str:
    data = text.encode('utf-8')
    header = f'blob {len(data)}\0'.encode('ascii')
    return hashlib.sha1(header + data).hexdigest()


def replace_required(text: str, old: str, new: str, *, count: int = 1) -> str:
    actual = text.count(old)
    if actual != count:
        raise RuntimeError(f'expected {count} occurrence(s), found {actual}: {old[:100]!r}')
    return text.replace(old, new)


def main() -> None:
    text = TARGET.read_text()
    before = git_blob_sha(text)
    if before == AFTER_BLOB:
        print('R267_1_PARTIAL_RECEIPT_ALREADY_MATERIALIZED', AFTER_BLOB)
        return
    if before != BEFORE_BLOB:
        raise RuntimeError(f'refusing unexpected source blob: {before}')

    text = replace_required(
        text,
        "            final_validation_cases=len(terminal),\n            final_validation_exact=0,\n            reason='structure_discovery_failed',",
        "            final_validation_cases=0,\n            final_validation_exact=0,\n            reason='structure_discovery_failed',",
    )
    text = replace_required(
        text,
        '    planned_probe_validation_cases = len(validation) * len(selected.profiles)\n',
        '    probe_validation_cases = 0\n',
    )
    text = replace_required(
        text,
        "                probe_validation_cases=planned_probe_validation_cases,\n                probe_validation_exact=probe_validation_exact,\n                final_validation_cases=len(terminal),\n                final_validation_exact=0,\n                reason='probe_synthesis_failed',",
        "                probe_validation_cases=probe_validation_cases,\n                probe_validation_exact=probe_validation_exact,\n                final_validation_cases=0,\n                final_validation_exact=0,\n                reason='probe_synthesis_failed',",
    )
    text = replace_required(
        text,
        '        for context, expected in zip(validation, profile.validation_outputs, strict=True):\n            try:',
        '        for context, expected in zip(validation, profile.validation_outputs, strict=True):\n            probe_validation_cases += 1\n            try:',
    )
    text = replace_required(
        text,
        "            probe_validation_cases=planned_probe_validation_cases,\n            probe_validation_exact=probe_validation_exact,\n            final_validation_cases=len(terminal),\n            final_validation_exact=0,\n            reason='probe_validation_failed',",
        "            probe_validation_cases=probe_validation_cases,\n            probe_validation_exact=probe_validation_exact,\n            final_validation_cases=0,\n            final_validation_exact=0,\n            reason='probe_validation_failed',",
    )
    text = replace_required(
        text,
        "            probe_validation_cases=planned_probe_validation_cases,\n            probe_validation_exact=probe_validation_exact,\n            final_validation_cases=len(terminal),\n            final_validation_exact=0,\n            reason='substituted_validation_failed',",
        "            probe_validation_cases=probe_validation_cases,\n            probe_validation_exact=probe_validation_exact,\n            final_validation_cases=0,\n            final_validation_exact=0,\n            reason='substituted_validation_failed',",
    )
    text = replace_required(
        text,
        '    terminal_calls = 0\n    terminal_probe_exact = 0\n    final_exact = 0\n',
        '    terminal_calls = 0\n    terminal_probe_cases = 0\n    terminal_probe_exact = 0\n    final_cases = 0\n    final_exact = 0\n',
    )
    text = replace_required(
        text,
        '                if context_validator is not None and not bool(context_validator(intervened)):\n',
        '                terminal_probe_cases += 1\n                if context_validator is not None and not bool(context_validator(intervened)):\n',
    )
    text = replace_required(
        text,
        '                        probe_validation_cases=planned_probe_validation_cases,\n                        probe_validation_exact=probe_validation_exact,\n                        final_validation_cases=len(terminal),\n                        final_validation_exact=final_exact,',
        '                        probe_validation_cases=probe_validation_cases,\n                        probe_validation_exact=probe_validation_exact,\n                        final_validation_cases=final_cases,\n                        final_validation_exact=final_exact,',
    )
    text = replace_required(
        text,
        '                        terminal_probe_validation_cases=len(terminal) * 3,\n',
        '                        terminal_probe_validation_cases=terminal_probe_cases,\n',
    )
    text = replace_required(
        text,
        '            expected = terminal_oracle(context)\n',
        '            final_cases += 1\n            expected = terminal_oracle(context)\n',
    )
    text = replace_required(
        text,
        "            probe_validation_cases=planned_probe_validation_cases,\n            probe_validation_exact=probe_validation_exact,\n            final_validation_cases=len(terminal),\n            final_validation_exact=final_exact,\n            reason='independent_terminal_verification_error',",
        "            probe_validation_cases=probe_validation_cases,\n            probe_validation_exact=probe_validation_exact,\n            final_validation_cases=final_cases,\n            final_validation_exact=final_exact,\n            reason='independent_terminal_verification_error',",
        count=2,
    )
    text = replace_required(
        text,
        '            terminal_probe_validation_cases=len(terminal) * 3,\n',
        '            terminal_probe_validation_cases=terminal_probe_cases,\n',
        count=2,
    )
    text = replace_required(text, '    terminal_probe_cases = len(terminal) * 3\n', '')
    text = replace_required(
        text,
        '            probe_validation_cases=planned_probe_validation_cases,\n',
        '            probe_validation_cases=probe_validation_cases,\n',
        count=2,
    )
    text = replace_required(
        text,
        '            final_validation_cases=len(terminal),\n',
        '            final_validation_cases=final_cases,\n',
        count=2,
    )
    text = replace_required(text, '    if final_exact != len(terminal):\n', '    if final_exact != final_cases:\n')
    text = replace_required(
        text,
        '        probe_validation_cases=planned_probe_validation_cases,\n',
        '        probe_validation_cases=probe_validation_cases,\n',
    )
    text = replace_required(
        text,
        '        final_validation_cases=len(terminal),\n',
        '        final_validation_cases=final_cases,\n',
    )

    after = git_blob_sha(text)
    if after != AFTER_BLOB:
        raise RuntimeError(f'unexpected patched source blob: {after}')
    TARGET.write_text(text)
    print('R267_1_PARTIAL_RECEIPT_MATERIALIZED', before, after)


if __name__ == '__main__':
    main()
