from __future__ import annotations
import itertools,json,math
from dataclasses import dataclass
from typing import Mapping,Sequence
from .r256_operator_dsl import Binary,Const,Expr,Field,IfElse,Unary,evaluate_expr,expr_digest
from .r256_operator_invention import OperatorExample
from .r259_semantic_index_core import semantic_vector_key

_ARITHMETIC_OPS=('add','sub','mul','div','min','max')
_UNARY_OPS=('abs','neg')

def finite_json_value(value:object)->object:
    if isinstance(value,float) and not math.isfinite(value): raise ValueError('values must be finite')
    try: json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    except (TypeError,ValueError) as exc: raise TypeError('values must be finite JSON-compatible values') from exc
    return value

def equivalent(actual:object,expected:object)->bool:
    if isinstance(actual,(int,float)) and not isinstance(actual,bool) and isinstance(expected,(int,float)) and not isinstance(expected,bool):
        try:return math.isclose(float(actual),float(expected),rel_tol=1e-12,abs_tol=1e-12)
        except (TypeError,ValueError,OverflowError):return False
    return actual==expected

def semantic_key(values:Sequence[object])->str:
    return semantic_vector_key(tuple(finite_json_value(v) for v in values))

def used_fields(expr:Expr)->tuple[str,...]:
    out:set[str]=set()
    def walk(node:Expr)->None:
        if isinstance(node,Field):out.add(node.name)
        elif isinstance(node,Unary):walk(node.arg)
        elif isinstance(node,Binary):walk(node.left);walk(node.right)
        elif isinstance(node,IfElse):walk(node.condition);walk(node.when_true);walk(node.when_false)
    walk(expr);return tuple(sorted(out))

def evaluate_vector(expr:Expr,examples:Sequence[OperatorExample])->tuple[tuple[object,...]|None,int]:
    out=[];count=0
    for row in examples:
        try:value=finite_json_value(evaluate_expr(expr,row.context))
        except (ArithmeticError,KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError):return None,count+1
        count+=1;out.append(value)
    return tuple(out),count

def fold_binary(op:str,exprs:Sequence[Expr])->Expr:
    rows=tuple(exprs)
    if not rows:raise ValueError('cannot fold empty expression list')
    result=rows[0]
    for row in rows[1:]:result=Binary(op,result,row)
    return result

@dataclass(frozen=True,slots=True)
class ExpressionSearchReceipt:
    passed:bool;expression:Expr|None;candidates_considered:int;evaluations:int;semantic_candidates:int;reason:str
@dataclass(frozen=True,slots=True)
class _SemanticCandidate:
    expression:Expr;values:tuple[object,...];used_fields:frozenset[str]

def synthesize_variable_expression(field_names:Sequence[str],required_probe_fields:Sequence[str],constants:Sequence[object],examples:Sequence[OperatorExample],*,max_depth:int,max_candidates:int,beam_width:int)->ExpressionSearchReceipt:
    fields=tuple(dict.fromkeys(map(str,field_names)));required=frozenset(map(str,required_probe_fields));rows=tuple(examples);limit=int(max_candidates)
    if not fields or not rows:return ExpressionSearchReceipt(False,None,0,0,0,'variable_basis_no_expression')
    if not required<=set(fields):raise ValueError('required probe fields must be present in field_names')
    if limit<1:raise ValueError('max_candidates must be positive')
    max_depth=int(max_depth)
    if max_depth<0:raise ValueError('max_depth must be non-negative')
    beam_width=max(8,int(beam_width));target=tuple(finite_json_value(r.expected) for r in rows)
    considered=evaluations=0;seen:set[str]=set();semantic_best:dict[tuple[str,frozenset[str]],_SemanticCandidate]={};candidates:list[_SemanticCandidate]=[];exhausted=False
    def consider(expr:Expr)->ExpressionSearchReceipt|None:
        nonlocal considered,evaluations,exhausted
        if expr.depth>max_depth:return None
        digest=expr_digest(expr)
        if digest in seen:return None
        if considered>=limit:
            exhausted=True;return ExpressionSearchReceipt(False,None,considered,evaluations,len(semantic_best),'variable_basis_budget_exhausted')
        seen.add(digest);considered+=1;values,count=evaluate_vector(expr,rows);evaluations+=count
        if values is None:return None
        used=frozenset(used_fields(expr));key=(semantic_key(values),used&required);candidate=_SemanticCandidate(expr,values,used);previous=semantic_best.get(key)
        if previous is not None:
            if (previous.expression.cost,previous.expression.depth,expr_digest(previous.expression)) <= (expr.cost,expr.depth,digest):return None
            try:candidates.remove(previous)
            except ValueError:pass
        semantic_best[key]=candidate;candidates.append(candidate)
        if required<=used and all(equivalent(a,b) for a,b in zip(values,target,strict=True)):
            return ExpressionSearchReceipt(True,expr,considered,evaluations,len(semantic_best),'variable_basis_exact')
        return None
    for name in sorted(fields):
        hit=consider(Field(name))
        if hit is not None and hit.passed:return hit
    consts=[];const_keys=set()
    for raw in constants:
        try:value=finite_json_value(raw);key=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False);Const(value)
        except (TypeError,ValueError):continue
        if key in const_keys:continue
        const_keys.add(key);consts.append(value);hit=consider(Const(value))
        if hit is not None and hit.passed:return hit
    if required:
        aggregate=fold_binary('add',tuple(Field(name) for name in sorted(required)))
        hit=consider(aggregate)
        if hit is not None and hit.passed:return hit
        for value in consts:
            c=Const(value)
            for op in ('add','sub','mul','div'):
                for expr in (Binary(op,aggregate,c),Binary(op,c,aggregate)):
                    hit=consider(expr)
                    if hit is not None and (hit.passed or hit.reason.endswith('budget_exhausted')):return hit
    ordinary=tuple(name for name in fields if not name.startswith('__p'))
    if len(ordinary)>=2:
        products=tuple(Binary('mul',Field(a),Field(b)) for a,b in itertools.combinations(ordinary,2))
        for product in products:
            hit=consider(product)
            if hit is not None and hit.passed:return hit
        if len(products)>=2:
            aggregate=fold_binary('add',products);hit=consider(aggregate)
            if hit is not None and hit.passed:return hit
            for value in consts:
                c=Const(value)
                for op in ('add','sub','mul','div'):
                    for expr in (Binary(op,aggregate,c),Binary(op,c,aggregate)):
                        hit=consider(expr)
                        if hit is not None and (hit.passed or hit.reason.endswith('budget_exhausted')):return hit
    for depth in range(1,max_depth+1):
        if exhausted:break
        ranked=sorted(candidates,key=lambda r:(-len(r.used_fields&required),r.expression.cost,r.expression.depth,expr_digest(r.expression)))
        frontier=[r for r in ranked if r.expression.depth==depth-1][:beam_width];pool=ranked[:beam_width]
        if not frontier:continue
        for left in frontier:
            for op in _UNARY_OPS:
                hit=consider(Unary(op,left.expression))
                if hit is not None and (hit.passed or hit.reason.endswith('budget_exhausted')):return hit
            for right in pool:
                for op in _ARITHMETIC_OPS:
                    hit=consider(Binary(op,left.expression,right.expression))
                    if hit is not None and (hit.passed or hit.reason.endswith('budget_exhausted')):return hit
    return ExpressionSearchReceipt(False,None,considered,evaluations,len(semantic_best),'variable_basis_budget_exhausted' if exhausted else 'variable_basis_no_expression')

def rewrite_with_mapping(expr:Expr,mapping:Mapping[str,Expr])->Expr:
    if isinstance(expr,Field):return mapping.get(expr.name,expr)
    if isinstance(expr,Const):return expr
    if isinstance(expr,Unary):return Unary(expr.op,rewrite_with_mapping(expr.arg,mapping))
    if isinstance(expr,Binary):return Binary(expr.op,rewrite_with_mapping(expr.left,mapping),rewrite_with_mapping(expr.right,mapping))
    if isinstance(expr,IfElse):return IfElse(rewrite_with_mapping(expr.condition,mapping),rewrite_with_mapping(expr.when_true,mapping),rewrite_with_mapping(expr.when_false,mapping))
    raise TypeError(f'unsupported expression node: {type(expr).__name__}')
