from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

ExpectedRule = Callable[[Sequence[int], int], int]
GATES = ('seed', 'length', 'normal_recurrence', 'special_recurrence')
AES_CORE_DECOYS = ('core_no_rot', 'core_no_sub', 'core_wrong_rcon', 'core_rcon_low_byte')


@dataclass(frozen=True)
class PeriodicRecurrenceAdapter:
    domain_id: str
    seed: tuple[int, ...]
    expected_length: int
    period: int
    normal_expected: ExpectedRule
    special_expected: ExpectedRule
    mechanism_tags: tuple[str, ...] = ('guarded', 'periodic', 'recurrence')

    def __post_init__(self) -> None:
        if not str(self.domain_id).strip():
            raise ValueError('domain_id must be non-empty')
        if not self.seed:
            raise ValueError('seed must be non-empty')
        if self.period <= 0:
            raise ValueError('period must be positive')
        if self.expected_length <= len(self.seed):
            raise ValueError('expected_length must exceed seed length')
        if len(self.seed) != self.period:
            raise ValueError('seed length must equal recurrence period')


@dataclass(frozen=True)
class InvariantCheck:
    seed: bool
    length: bool
    normal_recurrence: bool
    special_recurrence: bool

    @property
    def passed(self) -> bool:
        return self.seed and self.length and self.normal_recurrence and self.special_recurrence

    def gate(self, name: str) -> bool:
        if name not in GATES:
            raise ValueError(f'unknown gate: {name}')
        return bool(getattr(self, name))


def check_periodic_recurrence(
    candidate: Sequence[int], adapter: PeriodicRecurrenceAdapter
) -> InvariantCheck:
    words = tuple(int(value) for value in candidate)
    seed_ok = len(words) >= len(adapter.seed) and words[: len(adapter.seed)] == adapter.seed
    length_ok = len(words) == adapter.expected_length
    normal_ok = True
    special_ok = True
    for index in range(len(adapter.seed), len(words)):
        if index % adapter.period == 0:
            expected = int(adapter.special_expected(words, index))
            if words[index] != expected:
                special_ok = False
        else:
            expected = int(adapter.normal_expected(words, index))
            if words[index] != expected:
                normal_ok = False
    return InvariantCheck(seed_ok, length_ok, normal_ok, special_ok)


def filter_cohort(
    cohort: Mapping[str, Sequence[int]],
    adapter: PeriodicRecurrenceAdapter,
    *,
    enabled: Iterable[str] = GATES,
) -> tuple[str, ...]:
    enabled_gates = tuple(enabled)
    unknown = set(enabled_gates) - set(GATES)
    if unknown:
        raise ValueError(f'unknown gates: {sorted(unknown)}')
    survivors = []
    for name, candidate in cohort.items():
        check = check_periodic_recurrence(candidate, adapter)
        if all(check.gate(gate) for gate in enabled_gates):
            survivors.append(str(name))
    return tuple(sorted(survivors))


# ---------------------------------------------------------------------------
# Synthetic source family. The verifier itself is domain-neutral; this family
# exists to establish the mechanism before any external-domain execution.
# ---------------------------------------------------------------------------

_SOURCE_MASK = 0xFFFF
_SOURCE_SEED = (0x0123, 0x4567, 0x89AB)


def _rot16(value: int) -> int:
    value &= _SOURCE_MASK
    return ((value << 5) & _SOURCE_MASK) | (value >> 11)


def _source_normal(words: Sequence[int], index: int) -> int:
    return (int(words[index - 3]) + int(words[index - 1])) & _SOURCE_MASK


def _source_special(words: Sequence[int], index: int) -> int:
    round_index = index // 3
    return (int(words[index - 3]) ^ _rot16(int(words[index - 1])) ^ (0x9E37 * round_index)) & _SOURCE_MASK


def _source_wrong_special(words: Sequence[int], index: int) -> int:
    round_index = index // 3
    return (int(words[index - 3]) ^ int(words[index - 1]) ^ (0x9E37 * round_index)) & _SOURCE_MASK


def _source_skipped_special(words: Sequence[int], index: int) -> int:
    return _source_normal(words, index)


def source_periodic_adapter() -> PeriodicRecurrenceAdapter:
    return PeriodicRecurrenceAdapter(
        'synthetic-periodic-recurrence',
        _SOURCE_SEED,
        18,
        3,
        _source_normal,
        _source_special,
    )


def _expand_source(special_rule: ExpectedRule) -> tuple[int, ...]:
    adapter = source_periodic_adapter()
    words = list(adapter.seed)
    for index in range(len(words), adapter.expected_length):
        if index % adapter.period == 0:
            words.append(int(special_rule(words, index)))
        else:
            words.append(int(adapter.normal_expected(words, index)))
    return tuple(words)


def make_source_recurrence_cohort() -> dict[str, tuple[int, ...]]:
    target = _expand_source(_source_special)
    wrong = _expand_source(_source_wrong_special)
    skipped = _expand_source(_source_skipped_special)
    bad_normal = list(target)
    bad_normal[7] ^= 1
    wrong_seed = list(target)
    wrong_seed[0] ^= 1
    return {
        'source_target': target,
        'source_wrong_special': wrong,
        'source_skipped_special': skipped,
        'source_bad_normal': tuple(bad_normal),
        'source_wrong_seed': tuple(wrong_seed),
        'source_truncated': target[:-1],
    }


# ---------------------------------------------------------------------------
# External transfer family: NIST FIPS 197-upd1, Appendix A.1 AES-128 schedule.
# The frozen NIST words are an independent fixture oracle. They are not used
# by check_periodic_recurrence or filter_cohort as an answer-equality gate.
# ---------------------------------------------------------------------------

NIST_SOURCE = {
    'publication': 'NIST FIPS 197-upd1',
    'appendix': 'Appendix A.1 — Expansion of a 128-bit Key',
    'updated': '2023-05-09',
}
NIST_AES128_KEY = bytes.fromhex('2b7e151628aed2a6abf7158809cf4f3c')
NIST_AES128_WORDS = (
    0x2B7E1516, 0x28AED2A6, 0xABF71588, 0x09CF4F3C,
    0xA0FAFE17, 0x88542CB1, 0x23A33939, 0x2A6C7605,
    0xF2C295F2, 0x7A96B943, 0x5935807A, 0x7359F67F,
    0x3D80477D, 0x4716FE3E, 0x1E237E44, 0x6D7A883B,
    0xEF44A541, 0xA8525B7F, 0xB671253B, 0xDB0BAD00,
    0xD4D1C6F8, 0x7C839D87, 0xCAF2B8BC, 0x11F915BC,
    0x6D88A37A, 0x110B3EFD, 0xDBF98641, 0xCA0093FD,
    0x4E54F70E, 0x5F5FC9F3, 0x84A64FB2, 0x4EA6DC4F,
    0xEAD27321, 0xB58DBAD2, 0x312BF560, 0x7F8D292F,
    0xAC7766F3, 0x19FADC21, 0x28D12941, 0x575C006E,
    0xD014F9A8, 0xC9EE2589, 0xE13F0CC8, 0xB6630CA6,
)

SBOX = (
    0x63,0x7C,0x77,0x7B,0xF2,0x6B,0x6F,0xC5,0x30,0x01,0x67,0x2B,0xFE,0xD7,0xAB,0x76,
    0xCA,0x82,0xC9,0x7D,0xFA,0x59,0x47,0xF0,0xAD,0xD4,0xA2,0xAF,0x9C,0xA4,0x72,0xC0,
    0xB7,0xFD,0x93,0x26,0x36,0x3F,0xF7,0xCC,0x34,0xA5,0xE5,0xF1,0x71,0xD8,0x31,0x15,
    0x04,0xC7,0x23,0xC3,0x18,0x96,0x05,0x9A,0x07,0x12,0x80,0xE2,0xEB,0x27,0xB2,0x75,
    0x09,0x83,0x2C,0x1A,0x1B,0x6E,0x5A,0xA0,0x52,0x3B,0xD6,0xB3,0x29,0xE3,0x2F,0x84,
    0x53,0xD1,0x00,0xED,0x20,0xFC,0xB1,0x5B,0x6A,0xCB,0xBE,0x39,0x4A,0x4C,0x58,0xCF,
    0xD0,0xEF,0xAA,0xFB,0x43,0x4D,0x33,0x85,0x45,0xF9,0x02,0x7F,0x50,0x3C,0x9F,0xA8,
    0x51,0xA3,0x40,0x8F,0x92,0x9D,0x38,0xF5,0xBC,0xB6,0xDA,0x21,0x10,0xFF,0xF3,0xD2,
    0xCD,0x0C,0x13,0xEC,0x5F,0x97,0x44,0x17,0xC4,0xA7,0x7E,0x3D,0x64,0x5D,0x19,0x73,
    0x60,0x81,0x4F,0xDC,0x22,0x2A,0x90,0x88,0x46,0xEE,0xB8,0x14,0xDE,0x5E,0x0B,0xDB,
    0xE0,0x32,0x3A,0x0A,0x49,0x06,0x24,0x5C,0xC2,0xD3,0xAC,0x62,0x91,0x95,0xE4,0x79,
    0xE7,0xC8,0x37,0x6D,0x8D,0xD5,0x4E,0xA9,0x6C,0x56,0xF4,0xEA,0x65,0x7A,0xAE,0x08,
    0xBA,0x78,0x25,0x2E,0x1C,0xA6,0xB4,0xC6,0xE8,0xDD,0x74,0x1F,0x4B,0xBD,0x8B,0x8A,
    0x70,0x3E,0xB5,0x66,0x48,0x03,0xF6,0x0E,0x61,0x35,0x57,0xB9,0x86,0xC1,0x1D,0x9E,
    0xE1,0xF8,0x98,0x11,0x69,0xD9,0x8E,0x94,0x9B,0x1E,0x87,0xE9,0xCE,0x55,0x28,0xDF,
    0x8C,0xA1,0x89,0x0D,0xBF,0xE6,0x42,0x68,0x41,0x99,0x2D,0x0F,0xB0,0x54,0xBB,0x16,
)
RCON = (0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def _rot_word(word: int) -> int:
    return ((word << 8) & 0xFFFFFFFF) | (word >> 24)


def _sub_word(word: int) -> int:
    return (
        (SBOX[(word >> 24) & 0xFF] << 24)
        | (SBOX[(word >> 16) & 0xFF] << 16)
        | (SBOX[(word >> 8) & 0xFF] << 8)
        | SBOX[word & 0xFF]
    )


def _aes_core_standard(prev: int, round_index: int) -> int:
    return _sub_word(_rot_word(prev)) ^ (RCON[round_index] << 24)


def _aes_core_no_rot(prev: int, round_index: int) -> int:
    return _sub_word(prev) ^ (RCON[round_index] << 24)


def _aes_core_no_sub(prev: int, round_index: int) -> int:
    return _rot_word(prev) ^ (RCON[round_index] << 24)


def _aes_core_wrong_rcon(prev: int, round_index: int) -> int:
    wrong = RCON[(round_index % 10) + 1]
    return _sub_word(_rot_word(prev)) ^ (wrong << 24)


def _aes_core_rcon_low_byte(prev: int, round_index: int) -> int:
    return _sub_word(_rot_word(prev)) ^ RCON[round_index]


def _aes_key_words(key: bytes) -> tuple[int, ...]:
    if len(key) != 16:
        raise ValueError('AES-128 key must be exactly 16 bytes')
    return tuple(int.from_bytes(key[i : i + 4], 'big') for i in range(0, 16, 4))


def _aes_normal(words: Sequence[int], index: int) -> int:
    return (int(words[index - 4]) ^ int(words[index - 1])) & 0xFFFFFFFF


def _aes_special(words: Sequence[int], index: int) -> int:
    return (int(words[index - 4]) ^ _aes_core_standard(int(words[index - 1]), index // 4)) & 0xFFFFFFFF


def aes128_nist_adapter() -> PeriodicRecurrenceAdapter:
    return PeriodicRecurrenceAdapter(
        'nist-aes128-key-schedule',
        _aes_key_words(NIST_AES128_KEY),
        44,
        4,
        _aes_normal,
        _aes_special,
        ('finite-field', 'guarded', 'periodic', 'recurrence'),
    )


def _expand_aes(core: Callable[[int, int], int] = _aes_core_standard, *, bad_normal: bool = False) -> tuple[int, ...]:
    words = list(_aes_key_words(NIST_AES128_KEY))
    for index in range(4, 44):
        if index % 4 == 0:
            expected = words[index - 4] ^ core(words[index - 1], index // 4)
        else:
            prev = words[index - 1]
            if bad_normal:
                prev ^= 1 << ((index % 4) * 8)
            expected = words[index - 4] ^ prev
        words.append(expected & 0xFFFFFFFF)
    return tuple(words)


def make_aes128_nist_cohort() -> dict[str, tuple[int, ...]]:
    wrong_key = bytes([NIST_AES128_KEY[0] ^ 1]) + NIST_AES128_KEY[1:]
    wrong_seed = list(_expand_aes())
    wrong_seed[:4] = _aes_key_words(wrong_key)
    # Recompute the suffix under the new seed, so the seed gate—not a broken
    # recurrence—is what distinguishes this candidate.
    seeded = list(_aes_key_words(wrong_key))
    for index in range(4, 44):
        if index % 4 == 0:
            value = seeded[index - 4] ^ _aes_core_standard(seeded[index - 1], index // 4)
        else:
            value = seeded[index - 4] ^ seeded[index - 1]
        seeded.append(value & 0xFFFFFFFF)
    return {
        'target_nist_fips197': NIST_AES128_WORDS,
        'core_no_rot': _expand_aes(_aes_core_no_rot),
        'core_no_sub': _expand_aes(_aes_core_no_sub),
        'core_wrong_rcon': _expand_aes(_aes_core_wrong_rcon),
        'core_rcon_low_byte': _expand_aes(_aes_core_rcon_low_byte),
        'bad_normal': _expand_aes(bad_normal=True),
        'wrong_seed': tuple(seeded),
        'truncated': NIST_AES128_WORDS[:-1],
    }
