from __future__ import annotations
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Mapping
from .authority import AuthorityGraph
from .events import EventLedger
from .registry import AgentRegistry
from .types import EventKind, canonical_digest

class ConflictStatus(str, Enum):
    OPEN='open'; READY_FOR_DECISION='ready_for_decision'; RESOLVED='resolved'; ESCALATED='escalated'

@dataclass(frozen=True, slots=True)
class ConflictClaim:
    claim_id:str; conflict_id:str; claimant_agent_id:str; region:str; proposition:str
    requested_action:str; evidence_refs:tuple[str,...]; event_id:str; digest:str
    def payload(self):
        return {'claim_id':self.claim_id,'conflict_id':self.conflict_id,'claimant_agent_id':self.claimant_agent_id,
                'region':self.region,'proposition':self.proposition,'requested_action':self.requested_action,
                'evidence_refs':list(self.evidence_refs),'event_id':self.event_id}
    def to_state(self): return {**self.payload(),'digest':self.digest}
    @classmethod
    def from_state(cls,s):
        r=cls(str(s['claim_id']),str(s['conflict_id']),str(s['claimant_agent_id']),str(s['region']),
              str(s['proposition']),str(s['requested_action']),tuple(str(x) for x in s.get('evidence_refs',())),
              str(s['event_id']),str(s['digest']))
        if canonical_digest(r.payload())!=r.digest: raise ValueError('conflict claim digest mismatch')
        return r

@dataclass(frozen=True, slots=True)
class ConflictResolutionReceipt:
    resolution_id:str; conflict_id:str; resolver_agent_id:str; decision:str
    evidence_refs:tuple[str,...]; override_id:str|None; event_id:str; digest:str
    def payload(self):
        return {'resolution_id':self.resolution_id,'conflict_id':self.conflict_id,'resolver_agent_id':self.resolver_agent_id,
                'decision':self.decision,'evidence_refs':list(self.evidence_refs),'override_id':self.override_id,'event_id':self.event_id}
    def to_state(self): return {**self.payload(),'digest':self.digest}
    @classmethod
    def from_state(cls,s):
        r=cls(str(s['resolution_id']),str(s['conflict_id']),str(s['resolver_agent_id']),str(s['decision']),
              tuple(str(x) for x in s.get('evidence_refs',())),None if s.get('override_id') is None else str(s['override_id']),
              str(s['event_id']),str(s['digest']))
        if canonical_digest(r.payload())!=r.digest: raise ValueError('conflict resolution digest mismatch')
        return r

@dataclass(frozen=True, slots=True)
class ConflictPacket:
    conflict_id:str; subject_artifact_id:str; owner_agent_id:str; opener_agent_id:str; status:ConflictStatus
    claim_ids:tuple[str,...]; causal_event_ids:tuple[str,...]; opened_event_id:str; resolution_id:str|None; digest:str
    def payload(self):
        return {'conflict_id':self.conflict_id,'subject_artifact_id':self.subject_artifact_id,'owner_agent_id':self.owner_agent_id,
                'opener_agent_id':self.opener_agent_id,'status':self.status.value,'claim_ids':list(self.claim_ids),
                'causal_event_ids':list(self.causal_event_ids),'opened_event_id':self.opened_event_id,'resolution_id':self.resolution_id}
    def to_state(self): return {**self.payload(),'digest':self.digest}
    @classmethod
    def from_state(cls,s):
        r=cls(str(s['conflict_id']),str(s['subject_artifact_id']),str(s['owner_agent_id']),str(s['opener_agent_id']),
              ConflictStatus(str(s['status'])),tuple(str(x) for x in s.get('claim_ids',())),
              tuple(str(x) for x in s.get('causal_event_ids',())),str(s['opened_event_id']),
              None if s.get('resolution_id') is None else str(s['resolution_id']),str(s['digest']))
        if canonical_digest(r.payload())!=r.digest: raise ValueError('conflict packet digest mismatch')
        return r

def _signed(row):
    return replace(row,digest=canonical_digest(row.payload()))

class ConflictCoordinator:
    def __init__(self,*,registry:AgentRegistry,authority:AuthorityGraph,events:EventLedger,
                 packets=(),claims=(),resolutions=(),conflict_counter=0,claim_counter=0,resolution_counter=0):
        self.registry=registry; self.authority=authority; self.events=events
        self._packets={x.conflict_id:x for x in packets}; self._claims={x.claim_id:x for x in claims}
        self._resolutions={x.resolution_id:x for x in resolutions}; self._claim_keys={}
        self._conflict_counter=int(conflict_counter); self._claim_counter=int(claim_counter); self._resolution_counter=int(resolution_counter)
        if self._conflict_counter<len(self._packets) or self._claim_counter<len(self._claims) or self._resolution_counter<len(self._resolutions):
            raise ValueError('conflict counters are not canonical')
        for p in packets:
            registry.get(p.owner_agent_id); registry.get(p.opener_agent_id); events.get(p.opened_event_id)
            if authority.owner_of(p.subject_artifact_id)!=p.owner_agent_id: raise ValueError('conflict owner mismatch')
            for e in p.causal_event_ids: events.get(e)
        for c in claims:
            p=self._packets.get(c.conflict_id)
            if p is None or c.claim_id not in p.claim_ids: raise ValueError('orphan conflict claim')
            if registry.get(c.claimant_agent_id).region!=c.region: raise ValueError('conflict region mismatch')
            events.get(c.event_id)
            self._claim_keys[(c.conflict_id,c.claimant_agent_id,c.proposition,c.requested_action,c.evidence_refs)]=c.claim_id
        for r in resolutions:
            p=self._packets.get(r.conflict_id)
            if p is None or p.resolution_id!=r.resolution_id: raise ValueError('orphan conflict resolution')
            if events.get(r.event_id).kind is not EventKind.CONFLICT_RESOLVED: raise ValueError('resolution event mismatch')
            authority.require_write(r.resolver_agent_id,p.subject_artifact_id,override_id=r.override_id)

    def open(self,opener_agent_id,subject_artifact_id,*,proposition,requested_action,evidence_refs=(),causal_event_ids=()):
        opener=self.registry.get(opener_agent_id); artifact=str(subject_artifact_id); owner=self.authority.owner_of(artifact)
        if owner is None: raise ValueError(f'artifact {artifact} has no authoritative owner')
        self.registry.get(owner); proposition=str(proposition).strip(); requested_action=str(requested_action).strip()
        if not proposition or not requested_action: raise ValueError('conflict claim must be explicit')
        for e in causal_event_ids: self.events.get(e)
        self._conflict_counter+=1; cid=f'conflict-{self._conflict_counter:08d}'
        self._claim_counter+=1; claim_id=f'claim-{self._claim_counter:08d}'
        ev=self.events.append(EventKind.CONFLICT_OPENED,source_agent_id=opener.agent_id,target_agent_id=owner,
            region=self.registry.get(owner).region,causal_parent_ids=tuple(str(x) for x in causal_event_ids),
            object_refs=(artifact,),evidence_refs=tuple(str(x) for x in evidence_refs),requires_ack=True,
            payload={'conflict_id':cid,'claim_id':claim_id,'proposition':proposition,'requested_action':requested_action})
        claim=_signed(ConflictClaim(claim_id,cid,opener.agent_id,opener.region,proposition,requested_action,
                    tuple(str(x) for x in evidence_refs),ev.event_id,''))
        packet=_signed(ConflictPacket(cid,artifact,owner,opener.agent_id,ConflictStatus.OPEN,(claim_id,),
                     tuple(str(x) for x in causal_event_ids),ev.event_id,None,''))
        self._claims[claim_id]=claim; self._packets[cid]=packet
        self._claim_keys[(cid,opener.agent_id,proposition,requested_action,claim.evidence_refs)]=claim_id
        return packet

    def add_claim(self,conflict_id,claimant_agent_id,*,proposition,requested_action,evidence_refs=()):
        p=self.get(conflict_id)
        if p.status is ConflictStatus.RESOLVED: raise ValueError('resolved conflict packet is immutable')
        a=self.registry.get(claimant_agent_id); proposition=str(proposition).strip(); requested_action=str(requested_action).strip()
        evidence=tuple(str(x) for x in evidence_refs); key=(p.conflict_id,a.agent_id,proposition,requested_action,evidence)
        if key in self._claim_keys: return self._claims[self._claim_keys[key]]
        if not proposition or not requested_action: raise ValueError('conflict claim must be explicit')
        self._claim_counter+=1; claim_id=f'claim-{self._claim_counter:08d}'
        ev=self.events.append(EventKind.CONFLICT_CLAIM_ADDED,source_agent_id=a.agent_id,target_agent_id=p.owner_agent_id,
            region=self.registry.get(p.owner_agent_id).region,causal_parent_ids=(p.opened_event_id,),
            object_refs=(p.subject_artifact_id,),evidence_refs=evidence,
            payload={'conflict_id':p.conflict_id,'claim_id':claim_id,'proposition':proposition,'requested_action':requested_action})
        c=_signed(ConflictClaim(claim_id,p.conflict_id,a.agent_id,a.region,proposition,requested_action,evidence,ev.event_id,''))
        self._claims[claim_id]=c; self._claim_keys[key]=claim_id
        self._packets[p.conflict_id]=_signed(replace(p,status=ConflictStatus.READY_FOR_DECISION,claim_ids=p.claim_ids+(claim_id,),digest=''))
        return c

    def resolve(self,conflict_id,resolver_agent_id,*,decision,evidence_refs,override_id=None):
        p=self.get(conflict_id)
        if p.status is ConflictStatus.RESOLVED: raise ValueError('conflict already resolved')
        resolver=self.registry.get(resolver_agent_id); decision=str(decision).strip()
        evidence=tuple(str(x) for x in evidence_refs if str(x).strip())
        if not decision or not evidence: raise ValueError('resolution requires decision and evidence')
        self.authority.require_write(resolver.agent_id,p.subject_artifact_id,override_id=override_id)
        self._resolution_counter+=1; rid=f'resolution-{self._resolution_counter:08d}'
        parents=tuple(dict.fromkeys((p.opened_event_id,)+tuple(self._claims[x].event_id for x in p.claim_ids)))
        ev=self.events.append(EventKind.CONFLICT_RESOLVED,source_agent_id=resolver.agent_id,target_agent_id=p.opener_agent_id,
            region=self.registry.get(p.owner_agent_id).region,causal_parent_ids=parents,object_refs=(p.subject_artifact_id,),
            evidence_refs=evidence,payload={'conflict_id':p.conflict_id,'resolution_id':rid,'decision':decision,'override_id':override_id})
        r=_signed(ConflictResolutionReceipt(rid,p.conflict_id,resolver.agent_id,decision,evidence,
                  None if override_id is None else str(override_id),ev.event_id,''))
        self._resolutions[rid]=r
        self._packets[p.conflict_id]=_signed(replace(p,status=ConflictStatus.RESOLVED,resolution_id=rid,digest=''))
        return r

    def get(self,conflict_id):
        try: return self._packets[str(conflict_id)]
        except KeyError as e: raise KeyError(f'unknown conflict id: {conflict_id}') from e
    def packets(self): return tuple(self._packets[k] for k in sorted(self._packets))
    def to_state(self):
        return {'packets':[x.to_state() for x in self.packets()],'claims':[self._claims[k].to_state() for k in sorted(self._claims)],
                'resolutions':[self._resolutions[k].to_state() for k in sorted(self._resolutions)],
                'conflict_counter':self._conflict_counter,'claim_counter':self._claim_counter,'resolution_counter':self._resolution_counter}
    @classmethod
    def from_state(cls,*,registry,authority,events,state:Mapping[str,Any]):
        ps=tuple(ConflictPacket.from_state(x) for x in state.get('packets',()))
        cs=tuple(ConflictClaim.from_state(x) for x in state.get('claims',()))
        rs=tuple(ConflictResolutionReceipt.from_state(x) for x in state.get('resolutions',()))
        return cls(registry=registry,authority=authority,events=events,packets=ps,claims=cs,resolutions=rs,
                   conflict_counter=int(state.get('conflict_counter',len(ps))),claim_counter=int(state.get('claim_counter',len(cs))),
                   resolution_counter=int(state.get('resolution_counter',len(rs))))
