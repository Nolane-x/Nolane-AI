from __future__ import annotations

from pathlib import Path

SOURCE = Path('cogcoder/r269_scoped_promotion.py')
SCOPED_TEST = Path('tests/test_r269_scoped_promotion.py')
REGISTRY_TEST = Path('tests/test_r269_promotion_registry.py')
AUTH = '1f' * 32


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


def patch_source() -> None:
    text = SOURCE.read_text(encoding='utf-8')
    if 'verifier_authority_digest: str' not in text:
        text = replace_once(
            text,
            "        raise ValueError('structural_class_digest must be one exact 64-hex structural scope digest')\n    return text\n\n\ndef _sha",
            "        raise ValueError('structural_class_digest must be one exact 64-hex structural scope digest')\n    return text\n\n\ndef _authority(value: object) -> str:\n    text = _nonempty(value, 'verifier_authority_digest').lower()\n    if _HEX64.fullmatch(text) is None:\n        raise ValueError('verifier_authority_digest must be one exact 64-hex host authority digest')\n    return text\n\n\ndef _sha",
            'authority helper',
        )
        text = replace_once(
            text,
            "    candidate_issuer: str\n    verifier_issuer: str\n    heldout_targets: int\n",
            "    candidate_issuer: str\n    verifier_issuer: str\n    verifier_authority_digest: str\n    heldout_targets: int\n",
            'evidence field',
        )
        text = replace_once(
            text,
            "        object.__setattr__(self, 'candidate_issuer', _nonempty(self.candidate_issuer, 'candidate_issuer'))\n        object.__setattr__(self, 'verifier_issuer', _nonempty(self.verifier_issuer, 'verifier_issuer'))\n        if self.heldout_targets < 1:\n",
            "        object.__setattr__(self, 'candidate_issuer', _nonempty(self.candidate_issuer, 'candidate_issuer'))\n        object.__setattr__(self, 'verifier_issuer', _nonempty(self.verifier_issuer, 'verifier_issuer'))\n        object.__setattr__(self, 'verifier_authority_digest', _authority(self.verifier_authority_digest))\n        if self.heldout_targets < 1:\n",
            'evidence validation',
        )
        text = replace_once(
            text,
            "            'candidate_issuer': self.candidate_issuer,\n            'verifier_issuer': self.verifier_issuer,\n            'heldout_targets': self.heldout_targets,\n",
            "            'candidate_issuer': self.candidate_issuer,\n            'verifier_issuer': self.verifier_issuer,\n            'verifier_authority_digest': self.verifier_authority_digest,\n            'heldout_targets': self.heldout_targets,\n",
            'evidence digest binding',
        )
        text = replace_once(
            text,
            "class ScopedPromotionController:\n    def adjudicate(self, candidate: PromotionCandidate, evidence: ChampionChallengerEvidence) -> PromotionDecision:\n",
            "class ScopedPromotionController:\n    def __init__(self, *, trusted_verifier_authority_digests: frozenset[str] = frozenset()) -> None:\n        if not isinstance(trusted_verifier_authority_digests, frozenset):\n            raise TypeError('trusted_verifier_authority_digests must be frozenset')\n        self._trusted_verifier_authority_digests = frozenset(\n            _authority(row) for row in trusted_verifier_authority_digests\n        )\n\n    @property\n    def trusted_verifier_authority_digests(self) -> frozenset[str]:\n        return self._trusted_verifier_authority_digests\n\n    def adjudicate(self, candidate: PromotionCandidate, evidence: ChampionChallengerEvidence) -> PromotionDecision:\n",
            'controller trust store',
        )
        text = replace_once(
            text,
            "        elif evidence.candidate_issuer == evidence.verifier_issuer:\n            promoted, reason = False, 'independent_verifier_required'\n        elif evidence.champion_accepted_targets < 1:\n",
            "        elif evidence.candidate_issuer == evidence.verifier_issuer:\n            promoted, reason = False, 'independent_verifier_required'\n        elif evidence.verifier_authority_digest not in self._trusted_verifier_authority_digests:\n            promoted, reason = False, 'untrusted_verifier_authority'\n        elif evidence.champion_accepted_targets < 1:\n",
            'controller authority gate',
        )
    compile(text, str(SOURCE), 'exec')
    SOURCE.write_text(text, encoding='utf-8')


def patch_test(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    if 'VERIFIER_AUTHORITY' not in text:
        if path == SCOPED_TEST:
            text = replace_once(
                text,
                'OTHER_SCOPE = "71cd4002f92c4a4668c0b6dbc914a4dac25cba00d91cde8490c93232eaa042b1"\n',
                'OTHER_SCOPE = "71cd4002f92c4a4668c0b6dbc914a4dac25cba00d91cde8490c93232eaa042b1"\nVERIFIER_AUTHORITY = "' + AUTH + '"\n',
                'scoped test authority constant',
            )
        else:
            text = replace_once(
                text,
                'SCOPE = "4f5a56f01b9b9d4b57fe7f0e196f48c3cb0f8f088ee409160840ba8ab58f1db8"\n',
                'SCOPE = "4f5a56f01b9b9d4b57fe7f0e196f48c3cb0f8f088ee409160840ba8ab58f1db8"\nVERIFIER_AUTHORITY = "' + AUTH + '"\n',
                'registry test authority constant',
            )
        text = text.replace(
            '        verifier_issuer="issuer.independent",\n',
            '        verifier_issuer="issuer.independent",\n        verifier_authority_digest=VERIFIER_AUTHORITY,\n',
        )
        text = text.replace(
            'ScopedPromotionController().adjudicate',
            'ScopedPromotionController(trusted_verifier_authority_digests=frozenset({VERIFIER_AUTHORITY})).adjudicate',
        )
    compile(text, str(path), 'exec')
    path.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    patch_source()
    patch_test(SCOPED_TEST)
    patch_test(REGISTRY_TEST)
    print('R269_PROMOTION_VERIFIER_AUTHORITY_PATCHED')
