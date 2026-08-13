from __future__ import annotations
from .r20i_causal_discovery import run_r20i_episode
from .retrieval_microcycle import CognitionTimeRetriever, KnowledgeNeed
from .generation_retrieval import GenerationRetrievalHook

class R21Runtime:
    """Behavior-preserving R2.0i wrapper with optional cognition-time knowledge access."""
    new_neural_parameters=0
    effective_neural_parameters=78_779_253
    def __init__(self,parent,rollout,executive,*,knowledge_source=None,max_calls:int=8,top_k:int=3,max_chars:int=12000):
        self.parent=parent; self.rollout=rollout; self.executive=executive; self.knowledge_source=knowledge_source
        self._retriever=None if knowledge_source is None else CognitionTimeRetriever(knowledge_source,max_calls=max_calls,top_k=top_k,max_chars=max_chars)
    def run_episode(self,task,*,mode:str='hybrid_active_causal',beam_width:int=1,random_repeat:int=0):
        return run_r20i_episode(self.parent,self.rollout,self.executive,task,mode=mode,beam_width=beam_width,random_repeat=random_repeat)
    def retrieve(self,*,query:str,uncertainty:float,query_drift:float,novelty:float=1.0,use_anchors:bool=False,force:bool=False):
        if self._retriever is None: raise RuntimeError('no knowledge source is registered')
        return self._retriever.step(KnowledgeNeed(query,float(uncertainty),float(query_drift),float(novelty),bool(use_anchors),bool(force)))
    @property
    def evidence_ledger(self):
        return None if self._retriever is None else self._retriever.ledger
    def generation_hook(self,*,max_calls:int=8,top_k:int=3,max_chars:int=12000):
        if self.knowledge_source is None: raise RuntimeError('no knowledge source is registered')
        return GenerationRetrievalHook.from_source(self.knowledge_source,max_calls=max_calls,top_k=top_k,max_chars=max_chars)
