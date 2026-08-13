import json
import pytest

from cogcoder.r17_program_induction import (
    extract_demonstration_vector_pairs,
    extract_shallow_numeric_vector,
)


def test_extractors_are_field_name_agnostic_for_test_vector_and_demo_pairs():
    a={
        'demonstrations':[
            {'input':[0,1,2,3],'output':[1,2,3,4]},
            {'input':[4,3,2,1],'output':[5,4,3,2]},
        ],
        'test_state':[6,0,1,2],
        'step':0,
    }
    b={
        'examples':[
            {'foo':[0,1,2,3],'bar':[1,2,3,4]},
            {'foo':[4,3,2,1],'bar':[5,4,3,2]},
        ],
        'candidate_vector':[6,0,1,2],
        'clock':0,
    }
    assert extract_shallow_numeric_vector(json.dumps(a))==(6,0,1,2)
    assert extract_shallow_numeric_vector(json.dumps(b))==(6,0,1,2)
    assert extract_demonstration_vector_pairs(json.dumps(a))==extract_demonstration_vector_pairs(json.dumps(b))
    assert len(extract_demonstration_vector_pairs(json.dumps(a)))==2


def test_shallow_vector_extractor_refuses_ambiguous_same_depth_vectors():
    payload={'left':[0,1,2,3],'right':[4,5,6,0]}
    with pytest.raises(ValueError,match='ambiguous'):
        extract_shallow_numeric_vector(json.dumps(payload))


def test_demo_pair_extractor_keeps_pairs_unoriented_and_ignores_scalars_strings():
    payload={
        'examples':[{'a':[1,2],'b':[3,4],'note':'x'},{'a':[5,6],'b':[0,1],'score':1}],
        'test':[2,2],
        'actions':['x','y'],
    }
    pairs=extract_demonstration_vector_pairs(json.dumps(payload))
    assert pairs==[((1,2),(3,4)),((5,6),(0,1))]
