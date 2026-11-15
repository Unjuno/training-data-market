import json
from fastapi.testclient import TestClient
import pytest
from backend.store import GameStore
from backend.service import make_app

@pytest.fixture
def client_pair(tmp_path,monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*40)
    monkeypatch.setenv('TDM_ADMIN_KEY','a'*40)
    db=GameStore(tmp_path/'votes.sqlite3');db.initialize()
    db.bootstrap_samples([(i,i%10) for i in range(200)],'fixture')
    db.open_round('round-0001','initial',(3,5),5)
    with TestClient(make_app(db,tmp_path)) as alice, TestClient(make_app(db,tmp_path)) as bob:
        yield db,alice,bob


def test_private_forecast_persists_by_browser_and_scored_after_publish(client_pair):
    db,alice,bob=client_pair
    alice.get('/v1/rounds/current');bob.get('/v1/rounds/current')
    assert alice.get('/v1/rounds/round-0001/forecast/me').json()['probability_pct'] is None
    r=alice.put('/v1/rounds/round-0001/forecast/me',json={'probability_pct':80})
    assert r.status_code==200 and r.json()['status']=='created'
    assert alice.get('/v1/rounds/round-0001/forecast/me').json()['probability_pct']==80
    assert bob.get('/v1/rounds/round-0001/forecast/me').json()['probability_pct'] is None
    assert bob.put('/v1/rounds/round-0001/forecast/me',json={'probability_pct':25}).status_code==200
    assert alice.get('/v1/game/me').json()['total_points']==0
    db.lock_round('round-0001')
    assert alice.put('/v1/rounds/round-0001/forecast/me',json={'probability_pct':5}).status_code==409
    result={'has_votes':True,'community':{'target_loss':0.2},'random':{'target_loss':0.3}}
    token=db.claim_round('round-0001')
    db.finalize_round('round-0001',json.dumps(result),'round-0002','initial',(3,5),6,[],claim_token=token)
    assert alice.get('/v1/game/me').json()['total_points']==96
    assert bob.get('/v1/game/me').json()['total_points']==44
    assert alice.get('/v1/game/me').json()['items'][0]['outcome']=='community'


def test_forecast_api_rejects_invalid_probability_and_origin(client_pair):
    db,alice,_=client_pair
    for val in [-5,0,100,55.5,53,'70',True]:
        r=alice.put('/v1/rounds/round-0001/forecast/me',json={'probability_pct':val})
        assert r.status_code==422, (val,r.text)
    r=alice.put('/v1/rounds/round-0001/forecast/me',json={'probability_pct':70}, headers={'Origin':'https://evil.example'})
    assert r.status_code==403
    assert alice.get('/v1/rounds/unknown/forecast/me').status_code==404

def test_results_expose_authoritative_forecast_outcome(client_pair):
    db,alice,_=client_pair
    db.set_pick('round-0001','alice',3)
    db.lock_round('round-0001')
    token=db.claim_round('round-0001')
    db.finalize_round('round-0001',json.dumps({'has_votes':True,'community':{'target_loss':0.2},'random':{'target_loss':0.3},'promotion':'rollback'}),'round-0002','initial',(3,5),6,[],claim_token=token)
    r=alice.get('/v1/rounds/round-0001/results')
    assert r.status_code==200
    assert r.json()['results']['forecast_verdict']['outcome']=='community'
    assert r.json()['results']['promotion']=='rollback'
