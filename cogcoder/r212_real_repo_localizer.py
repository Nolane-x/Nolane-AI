from __future__ import annotations

import math
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Literal

Mode = Literal['path', 'hybrid']
MAX_BYTES, MAX_FILES, MAX_CHARS = 220_000, 12_000, 180_000
GRAPH_SEEDS, GRAPH_GAIN = 64, 0.14
EXCLUDED = frozenset('.git node_modules vendor vendors third_party third-party dist build out target coverage .venv venv __pycache__ .tox generated gen deps'.split())
BINARY = frozenset('.png .jpg .jpeg .gif .webp .pdf .zip .gz .bz2 .xz .7z .tar .jar .class .so .dll .dylib .a .o .obj .exe .bin .pt .onnx .wasm .woff .woff2 .ttf .mp3 .mp4 .pyc .sqlite .db'.split())
STOP = frozenset('the a an and or but if then else when where why how what which who to of in on for from with without into by as is are was were be been being this that these those it its we you they fix bug issue error wrong fails failure failed problem should would could can cannot does do did make use using used return value values add remove change update support new old more less after before while during around about related because due case cases test tests testing file files function method class code repo repository current expected actual behavior please need needs'.split())
TOKEN_RE = re.compile(r'[A-Za-z][A-Za-z0-9_.$:/\\-]{2,}')
SPAN_RE = re.compile(r'`([^`\n]{2,200})`|(?<![A-Za-z])["\']([^"\'\n]{3,160})["\']')
DEF_RE = re.compile(r'\b(?:class|struct|interface|enum|trait|type|def|func|fn|function)\s+([A-Za-z_][A-Za-z0-9_]*)')
REF_RES = (
    re.compile(r'\bfrom\s+([.A-Za-z_][.A-Za-z0-9_]*)\s+import\b'),
    re.compile(r'\bimport\s+([.A-Za-z_][.A-Za-z0-9_]*)'),
    re.compile(r'\brequire\s*\(\s*["\']([^"\']+)["\']'),
    re.compile(r'#\s*include\s*[<"]([^>"]+)[>"]'),
)


@dataclass(frozen=True)
class Anchor:
    term: str
    weight: float
    exact: bool = False


@dataclass(frozen=True)
class FileScore:
    path: str
    path_score: float
    content_score: float = 0.0
    symbol_score: float = 0.0
    graph_score: float = 0.0
    total_score: float = 0.0


def _parts(value: str) -> tuple[str, ...]:
    value = value.replace('\\', '/').strip('`"\'.,;:()[]{}<>')
    out: list[str] = []
    for chunk in re.split(r'[/._:\-]+', value):
        chunk = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', chunk)
        out.extend(p.lower() for p in chunk.split() if len(p) >= 3 and p.lower() not in STOP)
    return tuple(out)


def extract_issue_anchors(text: str) -> tuple[Anchor, ...]:
    best: dict[str, Anchor] = {}
    def add(term: str, weight: float, exact: bool = False) -> None:
        term = term.strip().replace('\\', '/').lower().strip('`"\'.,;:()[]{}<>')
        if len(term) < 3:
            return
        candidate = Anchor(term, weight, exact)
        old = best.get(term)
        if old is None or candidate.weight > old.weight or (exact and not old.exact):
            best[term] = candidate
    for match in SPAN_RE.finditer(text):
        span = next(x for x in match.groups() if x is not None)
        pathish = '/' in span or '\\' in span or bool(re.search(r'\.[A-Za-z0-9]{1,8}$', span))
        add(span, 9.0 if pathish else 7.0, True)
        for part in _parts(span):
            add(part, 4.5 if pathish else 4.0, True)
    for raw in TOKEN_RE.findall(text):
        low = raw.lower().strip('.,;:()[]{}<>')
        if len(low) < 3 or low in STOP:
            continue
        special = any(c.isupper() for c in raw[1:]) or any(c in raw for c in '_/.')
        add(raw, 2.2 if special else 1.0, special)
        for part in _parts(raw):
            add(part, 1.5 if special else 0.9)
    return tuple(sorted(best.values(), key=lambda x: (-x.weight, x.term)))


def _files(root: Path) -> list[str]:
    try:
        raw = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout
        paths = [p for p in raw.decode('utf-8', 'surrogateescape').split('\0') if p]
    except (OSError, subprocess.SubprocessError):
        paths = [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()]
    out: list[str] = []
    for rel in sorted(set(paths)):
        p = PurePosixPath(rel.replace('\\', '/'))
        if any(x.lower() in EXCLUDED for x in p.parts[:-1]) or p.suffix.lower() in BINARY or p.name.lower().endswith(('.min.js', '.min.css', '.map')):
            continue
        try:
            size = (root / rel).stat().st_size
        except OSError:
            continue
        if 0 < size <= MAX_BYTES:
            out.append(rel)
        if len(out) >= MAX_FILES:
            break
    return out


def _read(path: Path) -> str:
    try:
        raw = path.read_bytes()[:MAX_CHARS]
    except OSError:
        return ''
    return '' if b'\0' in raw[:8192] else raw.decode('utf-8', 'ignore')


def _path_score(path: str, anchors: tuple[Anchor, ...]) -> float:
    norm = path.replace('\\', '/').lower()
    tokens = set(_parts(path)) | {norm, PurePosixPath(path).name.lower(), PurePosixPath(path).stem.lower()}
    score = 0.0
    for a in anchors:
        if a.term == norm:
            score += 35 + 3 * a.weight
        elif '/' in a.term and a.term in norm:
            score += 16 + 2 * a.weight
        if a.term in tokens:
            score += 2.8 * a.weight
        else:
            score += 0.8 * a.weight * sum(p in tokens for p in _parts(a.term))
    return score


def _content_score(text: str, anchors: tuple[Anchor, ...]) -> tuple[float, float]:
    lower = text.lower()
    defs = {m.group(1).lower() for m in DEF_RE.finditer(text)}
    content = symbol = 0.0
    penalty = 1 / (1 + max(0.0, len(text) / 40_000 - 1) * 0.18)
    for a in anchors:
        count = 0 if '/' in a.term and a.term not in lower else min(lower.count(a.term), 6)
        if count:
            content += a.weight * (1 + math.log1p(count)) * (1.45 if a.exact else 1)
        if a.term in defs:
            symbol += 5.5 * a.weight
        else:
            symbol += 2.2 * a.weight * sum(p in defs for p in _parts(a.term))
    return content * penalty, symbol


def _refs(text: str) -> set[str]:
    out: set[str] = set()
    for rx in REF_RES:
        for m in rx.finditer(text):
            raw = m.group(1).strip().replace('\\', '/').lstrip('.')
            if raw and not raw.startswith(('http://', 'https://')):
                out.add(raw.lower()); out.update(_parts(raw))
    return out


def _neighbors(seed: str, refs: set[str], candidates: list[str]) -> set[str]:
    stems: dict[str, list[str]] = defaultdict(list)
    names: dict[str, list[str]] = defaultdict(list)
    for rel in candidates:
        p = PurePosixPath(rel); stems[p.stem.lower()].append(rel); names[p.name.lower()].append(rel)
    found: set[str] = set(); parent = PurePosixPath(seed).parent
    for ref in refs:
        norm = ref.replace('::', '/').replace('.', '/').strip('/'); last = norm.split('/')[-1] if norm else ''
        for key in {last, PurePosixPath(last).stem.lower()}:
            matches = stems.get(key, []) + names.get(key, [])
            if len(set(matches)) == 1: found.update(matches)
        for suffix in ('', '.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.c', '.cc', '.cpp', '.h', '.hpp', '.java'):
            guess = (parent / f'{norm}{suffix}').as_posix()
            if guess in candidates: found.add(guess)
    found.discard(seed)
    return found


def rank_repository_files(repo_dir: str | Path, problem_statement: str, mode: Mode = 'hybrid', *, top_k: int | None = None) -> list[FileScore]:
    if mode not in {'path', 'hybrid'}:
        raise ValueError("mode must be 'path' or 'hybrid'")
    root = Path(repo_dir); anchors = extract_issue_anchors(problem_statement); candidates = _files(root)
    scores: list[FileScore] = []; texts: dict[str, str] = {}
    for rel in candidates:
        ps = _path_score(rel, anchors)
        if mode == 'path':
            scores.append(FileScore(rel, ps, total_score=ps)); continue
        text = _read(root / rel); texts[rel] = text
        cs, ss = _content_score(text, anchors) if text else (0.0, 0.0)
        scores.append(FileScore(rel, ps, cs, ss, 0.0, ps + cs + ss))
    if mode == 'hybrid':
        extra: Counter[str] = Counter()
        for seed in sorted(scores, key=lambda x: (-x.total_score, x.path))[:GRAPH_SEEDS]:
            if seed.total_score <= 0: continue
            for neighbor in _neighbors(seed.path, _refs(texts.get(seed.path, '')), candidates):
                extra[neighbor] += GRAPH_GAIN * seed.total_score
        scores = [replace(x, graph_score=float(extra[x.path]), total_score=x.total_score + float(extra[x.path])) for x in scores]
    ranked = sorted(scores, key=lambda x: (-x.total_score, x.path))
    return ranked if top_k is None else ranked[:max(0, int(top_k))]
