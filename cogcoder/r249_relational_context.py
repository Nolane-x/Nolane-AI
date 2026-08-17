from __future__ import annotations

import ast
import hashlib
import itertools
from dataclasses import dataclass
from typing import Mapping, Sequence

from .r247_executable_patch_cegis import PatchCandidate, PatchMacro, _BINOPS, _CMPOPS, _digest, _parse_function, _wrap, infer_patch_macro


def _dump(node: ast.AST) -> str:
    return ast.dump(node, include_attributes=False)


def _parent_map(root: ast.AST) -> dict[ast.AST, ast.AST]:
    out: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(root):
        for child in ast.iter_child_nodes(parent):
            out[child] = parent
    return out


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def _assignment_alias_graph(fn: ast.FunctionDef) -> tuple[dict[str, ast.expr], dict[str, set[str]]]:
    defs: dict[str, ast.expr] = {}
    forward: dict[str, set[str]] = {}
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            target = n.targets[0].id
            defs[target] = n.value
            if isinstance(n.value, ast.Name):
                forward.setdefault(n.value.id, set()).add(target)
    return defs, forward


def _alias_closure(start: str, forward: Mapping[str, set[str]]) -> frozenset[str]:
    seen={start}; stack=[start]
    while stack:
        cur=stack.pop()
        for nxt in forward.get(cur, set()):
            if nxt not in seen:
                seen.add(nxt); stack.append(nxt)
    return frozenset(seen)


def _all_returns(fn: ast.FunctionDef) -> tuple[ast.Return, ...]:
    return tuple(n for n in ast.walk(fn) if isinstance(n, ast.Return) and n.value is not None)


def _site_assignment_target(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> str | None:
    cur=node
    while cur in parents:
        par=parents[cur]
        if isinstance(par, ast.Assign) and len(par.targets)==1 and isinstance(par.targets[0], ast.Name):
            return par.targets[0].id
        if isinstance(par, (ast.FunctionDef, ast.Lambda, ast.Return, ast.If)):
            break
        cur=par
    return None


def relational_features_for_site(fn: ast.FunctionDef, node: ast.AST) -> frozenset[str]:
    """Identifier-invariant graph/reachability features for a candidate edit site."""
    parents=_parent_map(fn); defs,forward=_assignment_alias_graph(fn); returns=_all_returns(fn)
    feats: set[str]=set()
    if isinstance(node, ast.BinOp):
        target=_site_assignment_target(node,parents)
        if target is None:
            return frozenset({'site:binop','assignment:no'})
        feats.update({'site:binop','assignment:yes'})
        lineage=_alias_closure(target,forward)
    elif isinstance(node, ast.Compare):
        feats.add('site:compare')
        if isinstance(node.left,ast.Name):
            lineage=_alias_closure(node.left.id,forward)
            if node.left.id in defs: feats.add('compare_left:defined')
        else:
            lineage=frozenset()
    else:
        return frozenset()

    guard_hits=[]
    for candidate in ast.walk(fn):
        if not isinstance(candidate,ast.If) or not isinstance(candidate.test,ast.Compare):
            continue
        test=candidate.test
        if not isinstance(test.left,ast.Name) or test.left.id not in lineage:
            continue
        guard_hits.append(candidate)
        feats.add('lineage:reaches_guard')
        if test.left.id != next(iter(lineage), test.left.id):
            feats.add('lineage:guard_via_alias')
        body_names=set()
        for ret in (n for n in ast.walk(ast.Module(body=candidate.body,type_ignores=[])) if isinstance(n,ast.Return) and n.value is not None):
            body_names |= _names(ret.value)
        if body_names & set(lineage):
            feats.add('guard_body:returns_lineage')
        if len(test.comparators)==1 and isinstance(test.comparators[0],ast.Name):
            threshold=test.comparators[0].id
            if any(threshold in _names(ret.value) for ret in returns if ret not in set(ast.walk(ast.Module(body=candidate.body,type_ignores=[])))):
                feats.add('guard_threshold:used_in_other_return')
    if len(lineage)>1: feats.add('lineage:has_alias')
    if len(lineage)>2: feats.add('lineage:multi_hop')
    if any(set(lineage)&_names(ret.value) for ret in returns): feats.add('lineage:reaches_return')
    if guard_hits: feats.add('guard:exists')
    return frozenset(feats)


def _candidate_nodes(fn: ast.FunctionDef, base: PatchMacro) -> tuple[ast.AST,...]:
    if base.slot in {'binop','operand_wrapper'}:
        nodes=[n for n in ast.walk(fn) if isinstance(n,ast.BinOp)]
        if base.slot=='binop':
            nodes=[n for n in nodes if type(n.op).__name__==base.src]
        else:
            nodes=[n for n in nodes if isinstance(n.left,ast.Name) and isinstance(n.right,ast.Name)]
        return tuple(nodes)
    if base.slot=='compare':
        return tuple(n for n in ast.walk(fn) if isinstance(n,ast.Compare) and len(n.ops)==1 and type(n.ops[0]).__name__==base.src)
    raise ValueError('unsupported relational slot')


def _changed_labels(before: ast.FunctionDef, after: ast.FunctionDef, base: PatchMacro) -> tuple[bool,...]:
    a=_candidate_nodes(before,base); b=_candidate_nodes(after,base)
    # For operand wrappers/replace, after candidates can disappear under src-filter. Align all raw nodes instead.
    typ=ast.BinOp if base.slot in {'binop','operand_wrapper'} else ast.Compare
    aa=[n for n in ast.walk(before) if isinstance(n,typ)]
    bb=[n for n in ast.walk(after) if isinstance(n,typ)]
    if len(aa)!=len(bb): raise ValueError('AST candidate count changed')
    label_by_id={id(x): _dump(x)!=_dump(y) for x,y in zip(aa,bb)}
    return tuple(bool(label_by_id[id(n)]) for n in a)


@dataclass(frozen=True, order=True)
class RelationalContextMacro:
    macro_id: str
    base: PatchMacro
    required_features: tuple[str,...]
    support: int
    positive_sites: int
    negative_sites: int

    def __post_init__(self):
        if not self.required_features: raise ValueError('predicate must require features')
        if int(self.support)<=0 or int(self.positive_sites)<=0: raise ValueError('support/positives must be positive')
        object.__setattr__(self,'required_features',tuple(sorted(set(self.required_features))))
        object.__setattr__(self,'support',int(self.support)); object.__setattr__(self,'positive_sites',int(self.positive_sites)); object.__setattr__(self,'negative_sites',int(self.negative_sites))
    @property
    def slot(self): return self.base.slot


def learn_relational_context_macro(demos: Sequence[tuple[str,str]]) -> RelationalContextMacro:
    if len(demos)<2: raise ValueError('at least two demos required')
    bases=[]; positives=[]; negatives=[]
    for before_src,after_src in demos:
        base=infer_patch_macro(before_src,after_src); bases.append(base)
        before=_parse_function(before_src); after=_parse_function(after_src)
        nodes=_candidate_nodes(before,base); labels=_changed_labels(before,after,base)
        if sum(labels)!=1: raise ValueError('each demo must contain exactly one positive site')
        for n,label in zip(nodes,labels):
            feats=relational_features_for_site(before,n)
            (positives if label else negatives).append(feats)
    sig=bases[0].signature
    if any(b.signature!=sig for b in bases): raise ValueError('demos disagree on base rewrite')
    common=set.intersection(*(set(p) for p in positives))
    if not common: raise ValueError('no common positive features')
    # Learn minimal conjunction that covers all positives and rejects all observed negatives.
    chosen=None
    for k in range(1,len(common)+1):
        for combo in itertools.combinations(sorted(common),k):
            if all(not set(combo).issubset(set(n)) for n in negatives):
                chosen=combo; break
        if chosen is not None: break
    if chosen is None: raise ValueError('feature vocabulary cannot separate positive/negative sites')
    payload='|'.join([*(str(v) for v in sig),*chosen])
    mid='rcp:'+hashlib.sha256(payload.encode()).hexdigest()[:20]
    base=bases[0]
    return RelationalContextMacro(mid,PatchMacro(base.macro_id,*base.signature,support=len(demos)),tuple(chosen),len(demos),len(positives),len(negatives))


def learn_relational_context_library(grouped_demos: Mapping[str,Sequence[tuple[str,str]]]) -> tuple[RelationalContextMacro,...]:
    return tuple(sorted((learn_relational_context_macro(demos) for _name,demos in sorted(grouped_demos.items())),key=lambda m:m.macro_id))


def _apply_base(node: ast.AST, base: PatchMacro) -> None:
    if isinstance(node,ast.BinOp):
        if base.slot=='binop' and base.dst in _BINOPS and type(node.op).__name__==base.src:
            node.op=_BINOPS[base.dst]()
        elif base.slot=='operand_wrapper' and isinstance(node.left,ast.Name) and isinstance(node.right,ast.Name):
            node.left=_wrap(node.left,str(base.dst)); node.right=_wrap(node.right,str(base.dst))
    elif isinstance(node,ast.Compare) and base.slot=='compare' and len(node.ops)==1 and base.dst in _CMPOPS and type(node.ops[0]).__name__==base.src:
        node.ops[0]=_CMPOPS[base.dst]()


def apply_relational_context_macros(source: str, macros: Sequence[RelationalContextMacro]) -> str:
    tree=ast.parse(source)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef))
    ordered=sorted(macros,key=lambda m:({'binop':0,'operand_wrapper':1,'compare':2}[m.slot],m.macro_id))
    for macro in ordered:
        # Recompute features after each edit. Base edit preserves graph names/CFG.
        candidates=_candidate_nodes(fn,macro.base)
        selected=[n for n in candidates if set(macro.required_features).issubset(relational_features_for_site(fn,n))]
        for node in selected: _apply_base(node,macro.base)
        ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n'


def enumerate_relational_candidates(source: str, macros: Sequence[RelationalContextMacro]) -> tuple[PatchCandidate,...]:
    by_slot={s:[] for s in ('binop','operand_wrapper','compare')}
    for m in macros: by_slot[m.slot].append(m)
    choices=[(None,*sorted(by_slot[s],key=lambda m:m.macro_id)) for s in ('binop','operand_wrapper','compare')]
    out={}
    for selection in itertools.product(*choices):
        selected=tuple(m for m in selection if m is not None)
        patched=apply_relational_context_macros(source,selected)
        ids=tuple(sorted(m.macro_id for m in selected)); cid='rpc:'+_digest('|'.join(ids)+'|'+patched)
        c=PatchCandidate(cid,ids,patched,sum(m.support for m in selected),len(selected))
        prior=out.get(patched)
        if prior is None or (c.edit_count,-c.support_score,c.macro_ids)<(prior.edit_count,-prior.support_score,prior.macro_ids): out[patched]=c
    return tuple(sorted(out.values(),key=lambda c:(c.edit_count,-c.support_score,c.macro_ids,c.candidate_id)))
