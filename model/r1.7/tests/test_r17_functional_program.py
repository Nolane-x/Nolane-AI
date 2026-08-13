import json

from cogcoder.r17_program_induction import (
    search_functional_program,
    infer_functional_program,
)


def test_search_returns_shortest_exact_functional_program():
    # 0: +1 mod7, 1: reverse, 2: identity
    def step(vectors, action):
        out=[]
        for vector in vectors:
            if action==0:
                out.append(tuple((x+1)%7 for x in vector))
            elif action==1:
                out.append(tuple(reversed(vector)))
            else:
                out.append(tuple(vector))
        return out
    inputs=[(0,1,2,3),(3,0,1,2)]
    targets=step(step(inputs,0),1)
    result=search_functional_program(list(zip(inputs,targets)),[0,1,2],step,max_horizon=4)
    assert result.exact is True
    assert result.sequence==(0,1)
    assert result.horizon==2


def test_search_prefers_shortest_when_longer_program_is_functionally_equivalent():
    def step(vectors, action):
        if action==0:
            return [tuple(reversed(v)) for v in vectors]
        return [tuple(v) for v in vectors]
    demos=[((0,1,2),(2,1,0)),((3,4,5),(5,4,3))]
    result=search_functional_program(demos,[0,1],step,max_horizon=4)
    assert result.exact
    assert result.sequence==(0,)


def test_inference_uses_both_global_demo_orientations_without_field_names():
    class FakeActionEncoder:
        def __call__(self, tokens):
            # action index is enough for fake executor; shape [1,A,640]
            import torch
            a=tokens.shape[1]
            out=torch.zeros(1,a,640)
            for i in range(a): out[0,i,0]=i
            return out
    class FakeModel:
        workspace_dim=640
        action_encoder=FakeActionEncoder()
        def program_execute_logits(self,vectors,action_embeddings):
            import torch
            b,l=vectors.shape
            logits=torch.full((b,l,16),-20.0)
            action=action_embeddings[:,0].round().long()
            for i in range(b):
                v=vectors[i].tolist()
                if int(action[i])==0: nxt=[(x+1)%7 for x in v]
                elif int(action[i])==1: nxt=list(reversed(v))
                else: nxt=v
                for j,x in enumerate(nxt): logits[i,j,x]=20.0
            return logits
    source=[(0,1,2,3),(3,2,1,0)]
    transformed=[tuple(reversed(tuple((x+1)%7 for x in v))) for v in source]
    payload={
        'examples':[{'z':list(y),'q':list(x)} for x,y in zip(source,transformed)],
        'candidate':[6,5,4,3],
    }
    result=infer_functional_program(
        FakeModel(),json.dumps(payload),
        ['add one modulo seven to each value','reverse vector order','submit answer'],
        max_horizon=4,
    )
    assert result.exact
    assert result.orientation==1
    assert result.sequence==(0,1)


def test_execute_hypothesis_runs_sequence_then_public_submit():
    from types import SimpleNamespace
    from cogcoder.r17_program_induction import FunctionalProgramHypothesis, execute_functional_program_hypothesis
    class FakeTask:
        action_descriptions=('increment state','submit current hypothesis')
        def __init__(self): self.value=0; self.done=False
        def step(self,index):
            if index==0:
                self.value+=1
                return SimpleNamespace(done=False,solved=False)
            self.done=True
            return SimpleNamespace(done=True,solved=self.value==1)
    task=FakeTask()
    result=execute_functional_program_hypothesis(task,FunctionalProgramHypothesis((0,),True,1))
    assert result['solved'] is True
    assert result['used_actions']==2
    assert result['pre_submit_actions']==1
