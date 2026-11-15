"""Player-specific round recap must use the *vote-selected* slice of a batch."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.service import make_app
from backend.store import GameStore


@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','x'*40)
    monkeypatch.setenv('TDM_ADMIN_KEY','y'*40)
    db=GameStore(tmp_path/'votes.sqlite3');db.initialize()
    db.bootstrap_samples([(i,i%10) for i in range(200)], 'fixture')
    db.open_round('round-0001','cp0',(3,5),11)
    with TestClient(make_app(db,tmp_path)) as a, TestClient(make_app(db,tmp_path)) as b:
        yield db,a,b


def test_private_recap_only_counts_vote_selected_images_not_random_fill(setup):
    db,alice,bob=setup
    alice.get('/v1/rounds/current');bob.get('/v1/rounds/current')
    for i in (3,5,7):
        assert alice.put(f'/v1/rounds/round-0001/picks/{i}').status_code==200
    assert bob.put('/v1/rounds/round-0001/picks/9').status_code==200
    pending=alice.get('/v1/rounds/round-0001/participation/me')
    assert pending.status_code==200
    assert pending.json()['recommended_count']==3
    assert pending.json()['adopted_count'] is None
    db.lock_round('round-0001')
    token=db.claim_round('round-0001')
    result={ 'has_votes':True, 'voted_ids':[3,9], 'selected_ids':[3,5,7,9],
             'community':{'target_loss':0.2}, 'random':{'target_loss':0.3}, 'promotion':'rollback'}
    db.finalize_round('round-0001',json.dumps(result),'round-0002','cp0',(3,5),12,[],claim_token=token)
    rec=alice.get('/v1/rounds/round-0001/participation/me')
    assert rec.status_code==200
    assert rec.json()['recommended_count']==3
    assert rec.json()['adopted_count']==1
    assert rec.json()['adopted_ids']==[3]
    assert rec.json()['status']=='PUBLISHED'
    assert bob.get('/v1/rounds/round-0001/participation/me').json()['adopted_ids']==[9]
    # Only the authenticated player's own recommendations are disclosed.
    assert 9 not in rec.json()['recommended_ids']


def test_legacy_results_without_adoption_provenance_are_unknown_not_zero(setup):
    db,alice,_=setup
    alice.get('/v1/rounds/current')
    alice.put('/v1/rounds/round-0001/picks/3')
    db.lock_round('round-0001'); token=db.claim_round('round-0001')
    db.finalize_round('round-0001',json.dumps({'selected_ids':[3], 'promotion':'rollback'}),
        'round-0002','cp0',(3,5),12,[],claim_token=token)
    summary=alice.get('/v1/rounds/round-0001/participation/me').json()
    assert summary['adopted_count'] is None
    assert summary['adopted_ids'] is None
    assert alice.get('/v1/rounds/unknown/participation/me').status_code==404
