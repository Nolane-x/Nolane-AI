from __future__ import annotations
from dataclasses import dataclass
from .retrieval_microcycle import CognitionTimeRetriever,KnowledgeNeed,RetrievalDecision
@dataclass(frozen=True)
class RetrievalHookEvent:
    phase:str; step_index:int; text:str; uncertainty:float; retrieved:bool=False; reason:str=''
class GenerationRetrievalHook:
    def __init__(self,retriever:CognitionTimeRetriever): self.retriever=retriever; self.events=[]; self._last_visible=''
    @classmethod
    def from_source(cls,source,**kwargs): return cls(CognitionTimeRetriever(source,**kwargs))
    def before_step(self,*,step_index:int,visible_text:str,uncertainty:float)->RetrievalDecision:
        previous=set(self._last_visible.casefold().split()); current=set(visible_text.casefold().split()); union=len(previous|current); drift=1.0 if not previous else len(previous^current)/max(1,union)
        decision=self.retriever.step(KnowledgeNeed(visible_text,uncertainty=float(uncertainty),query_drift=float(drift),use_anchors=bool(self.retriever.state.calls)))
        self.events.append(RetrievalHookEvent('before_step',step_index,visible_text,float(uncertainty),decision.retrieved,decision.reason)); self._last_visible=visible_text
        return decision
    def after_step(self,*,step_index:int,emitted_text:str,uncertainty:float)->None:
        self.events.append(RetrievalHookEvent('after_step',step_index,emitted_text,float(uncertainty),False,'observation'))
