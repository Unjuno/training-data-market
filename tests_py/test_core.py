import math
import pytest
from backend.core import split_ids, weakness_pair, assemble_arms, select_promotion


def test_fixed_stratified_partitions_cover_every_index():
    labels=[k for k in range(10) for _ in range(5000)] + [k for k in range(10) for _ in range(1000)]
    parts=split_ids(labels,seed=20261115)
    assert [len(parts[p]) for p in ['initial','public','safety','candidate','test']]==[2000,3000,2000,43000,10000]
    assert len(set().union(*(set(v) for v in parts.values())))==60000
    for key,ids in parts.items():
        assert len(ids)==len(set(ids))
        assert len({i for i in ids if labels[i]==3})=={'initial':200,'public':300,'safety':200,'candidate':4300,'test':1000}[key]


def test_weakness_pair_uses_bidirectional_rate_not_raw_count():
    confusion=[[0]*10 for _ in range(10)]
    for x in range(10): confusion[x][x]=10
    confusion[3][5]=9;confusion[5][3]=8
    confusion[0][1]=7;confusion[1][0]=7
    assert weakness_pair(confusion)==(3,5)


def test_vote_sampling_is_bounded_unique_deterministic_and_balanced():
    classes={i:i%10 for i in range(2000)}
    picks={i:25 if i%10==3 else 5 for i in range(500)}
    a=assemble_arms(classes,picks,seed=23)
    b=assemble_arms(classes,picks,seed=23)
    assert a==b
    assert len(a['community'])==len(a['random'])==128
    assert len(set(a['community']))==len(set(a['random']))==128
    assert len(a['voted'])<=64
    assert sum(classes[i]==3 for i in a['voted'])<=48
    assert set(a['voted']).issubset(picks)


def test_zero_votes_explicit_and_random_fallback():
    result=assemble_arms({i:i%10 for i in range(150)}, {}, seed=9)
    assert result['has_votes'] is False
    assert len(result['community'])==len(result['random'])==128


def test_promotion_prefers_safe_community_else_random_else_rollback():
    before={'overall_loss':0.8,'target_loss':1.2,'recall':[.6]*10}
    def arm(loss,target,recall_drop=0):
      return {'overall_loss':loss,'target_loss':target,'recall':[.6-recall_drop]*10}
    assert select_promotion(before,arm(.79,1.15),arm(.77,1.1))=='community'
    assert select_promotion(before,arm(.9,1.1),arm(.8,1.1))=='random'
    assert select_promotion(before,arm(.9,1.1),arm(.9,1.1))=='rollback'
    assert select_promotion(before,arm(.79,1.1,.06),arm(.78,1.1))=='random'
    assert select_promotion(before,arm(float('nan'),1.0),arm(.79,1.1))=='random'
