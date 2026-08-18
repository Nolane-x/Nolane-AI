from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Sequence

from cogcoder.r247_executable_patch_cegis import PatchMacro, _BINOPS, _CMPOPS, _wrap
from cogcoder.r252_repository_query import RepositoryPatchCandidate, compile_repository_candidate


@dataclass(frozen=True, slots=True)
class ExpansionMutation:
    mutation_id: str
    seed_candidate_id: str
    macro_id: str
    path: str
    site_index: int


@dataclass(frozen=True, slots=True)
class ExpansionCandidate:
    candidate: RepositoryPatchCandidate
    mutation: ExpansionMutation


def _macro_key(macro: PatchMacro) -> tuple[object, ...]:
    return (macro.slot, macro.kind, macro.src or '', macro.dst or '', macro.macro_id)


def _seed_key(seed: RepositoryPatchCandidate) -> tuple[object, ...]:
    payload = json.dumps(seed.files, separators=(',', ':'), ensure_ascii=False)
    return (hashlib.sha256(payload.encode('utf-8')).hexdigest(), seed.candidate_id)


def _compatible(node: ast.AST, macro: PatchMacro) -> bool:
    if macro.slot == 'binop' and macro.kind == 'replace':
        return isinstance(node, ast.BinOp) and type(node.op).__name__ == macro.src and macro.dst in _BINOPS
    if macro.slot == 'operand_wrapper' and macro.kind == 'wrap':
        return (
            isinstance(node, ast.BinOp)
            and isinstance(node.left, ast.Name)
            and isinstance(node.right, ast.Name)
            and macro.dst in {'abs', 'neg', 'max0'}
        )
    if macro.slot == 'compare' and macro.kind == 'replace':
        return (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and type(node.ops[0]).__name__ == macro.src
            and macro.dst in _CMPOPS
        )
    if macro.slot == 'return_wrapper' and macro.kind == 'wrap':
        return isinstance(node, ast.Return) and node.value is not None and macro.dst in {'abs', 'neg', 'max0'}
    return False


def _apply(node: ast.AST, macro: PatchMacro) -> None:
    if macro.slot == 'binop':
        assert isinstance(node, ast.BinOp)
        node.op = _BINOPS[str(macro.dst)]()
        return
    if macro.slot == 'operand_wrapper':
        assert isinstance(node, ast.BinOp)
        node.left = _wrap(node.left, str(macro.dst))
        node.right = _wrap(node.right, str(macro.dst))
        return
    if macro.slot == 'compare':
        assert isinstance(node, ast.Compare)
        node.ops[0] = _CMPOPS[str(macro.dst)]()
        return
    if macro.slot == 'return_wrapper':
        assert isinstance(node, ast.Return) and node.value is not None
        node.value = _wrap(node.value, str(macro.dst))
        return
    raise ValueError('unsupported patch macro')


def _mutation_id(seed: RepositoryPatchCandidate, macro: PatchMacro, path: str, site_index: int) -> str:
    payload = json.dumps(
        {
            'seed_candidate_id': seed.candidate_id,
            'macro_id': macro.macro_id,
            'path': path,
            'site_index': int(site_index),
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return 'r261m:' + hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _candidate_id(files: tuple[tuple[str, str], ...], mutation: ExpansionMutation) -> str:
    payload = json.dumps(
        {
            'files': files,
            'mutation': {
                'mutation_id': mutation.mutation_id,
                'seed_candidate_id': mutation.seed_candidate_id,
                'macro_id': mutation.macro_id,
                'path': mutation.path,
                'site_index': mutation.site_index,
            },
        },
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
    )
    return 'r261c:' + hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _mutate_one(
    seed: RepositoryPatchCandidate,
    macro: PatchMacro,
    path: str,
    site_index: int,
) -> ExpansionCandidate | None:
    source_by_path = dict(seed.files)
    if path not in source_by_path:
        return None
    tree = ast.parse(source_by_path[path], filename=path)
    sites = [node for node in ast.walk(tree) if _compatible(node, macro)]
    if site_index < 0 or site_index >= len(sites):
        return None
    _apply(sites[site_index], macro)
    ast.fix_missing_locations(tree)
    updated = dict(source_by_path)
    updated[path] = ast.unparse(tree) + '\n'
    files = tuple(sorted(updated.items()))
    mutation = ExpansionMutation(
        _mutation_id(seed, macro, path, site_index),
        seed.candidate_id,
        macro.macro_id,
        path,
        int(site_index),
    )
    candidate = RepositoryPatchCandidate(
        _candidate_id(files, mutation),
        tuple(sorted((*seed.macro_ids, macro.macro_id))),
        files,
        int(seed.support_score) + int(macro.support),
        int(seed.edit_count) + 1,
    )
    try:
        compile_repository_candidate(candidate)
    except Exception:
        return None
    return ExpansionCandidate(candidate, mutation)


def expand_repository_candidates(
    seeds: Sequence[RepositoryPatchCandidate],
    macros: Sequence[PatchMacro],
    *,
    max_generated_candidates: int = 256,
    max_sites_per_macro: int = 64,
) -> tuple[ExpansionCandidate, ...]:
    max_generated_candidates = int(max_generated_candidates)
    max_sites_per_macro = int(max_sites_per_macro)
    if max_generated_candidates < 0:
        raise ValueError('max_generated_candidates must be non-negative')
    if max_sites_per_macro < 0:
        raise ValueError('max_sites_per_macro must be non-negative')
    if max_generated_candidates == 0 or max_sites_per_macro == 0:
        return ()

    rows: list[ExpansionCandidate] = []
    seen_files: set[tuple[tuple[str, str], ...]] = set()
    for seed in sorted(tuple(seeds), key=_seed_key):
        for macro in sorted(tuple(macros), key=_macro_key):
            for path, source in sorted(seed.files):
                tree = ast.parse(source, filename=path)
                site_count = sum(1 for node in ast.walk(tree) if _compatible(node, macro))
                for site_index in range(min(site_count, max_sites_per_macro)):
                    row = _mutate_one(seed, macro, path, site_index)
                    if row is None or row.candidate.files in seen_files:
                        continue
                    seen_files.add(row.candidate.files)
                    rows.append(row)

    rows.sort(key=lambda row: (row.candidate.files, row.mutation.mutation_id, row.candidate.candidate_id))
    return tuple(rows[:max_generated_candidates])


__all__ = [
    'ExpansionMutation',
    'ExpansionCandidate',
    'expand_repository_candidates',
]
