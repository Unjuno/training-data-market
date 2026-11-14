import os
import pytest
from fastapi.testclient import TestClient
from backend.store import GameStore
from backend.service import make_app

@pytest.fixture
def app(tmp_path,monkeypatch):
    monkeypatch.setenv('TDM_ADMIN_KEY','test-key-'*5)
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*40)
    db=GameStore(tmp_path/'game.sqlite3');db.initialize()
    db.bootstrap_samples([(i,i%10) for i in range(200)],'fixture')
    db.open_round('r1','cp0',(3,5),21)
    return make_app(db, tmp_path)


def test_two_browsers_vote_server_side_and_lock(app):
    with TestClient(app) as alice, TestClient(app) as bob:
        alice.get('/v1/rounds/current')
        bob.get('/v1/rounds/current')
        assert alice.put('/v1/rounds/r1/picks/14').status_code==200
        assert bob.put('/v1/rounds/r1/picks/14').status_code==200
        assert alice.get('/v1/rounds/r1/picks/me').json()['ids']==[14]
        assert bob.get('/v1/rounds/r1/picks/me').json()['ids']==[14]
        response=alice.get('/v1/samples')
        assert response.status_code==200
        assert response.json()['total']==200
        assert not response.json()['items'][0].get('image_url')
        assert alice.post('/v1/admin/rounds/r1/lock').status_code==403
        assert alice.post('/v1/admin/rounds/r1/lock',headers={'X-Admin-Key':'test-key-'*5}).status_code==200
        assert alice.put('/v1/rounds/r1/picks/15').status_code==409


def test_uninitialized_instance_does_not_fake_results(tmp_path,monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*40)
    store=GameStore(tmp_path/'fresh.sqlite3');store.initialize()
    with TestClient(make_app(store,tmp_path)) as client:
        response=client.get('/v1/rounds/current')
        assert response.status_code==200
        assert response.json()['mode']=='UNINITIALIZED'
        assert response.json()['metrics'] is None
        assert client.get('/v1/samples').status_code==503


def test_api_pagination_search_and_history(app):
    with TestClient(app) as client:
        r=client.get('/v1/samples?limit=2&page=2&query=14')
        assert r.status_code==200
        assert r.json()['limit']==2
        assert r.json()['total']>0
        hist=client.get('/v1/rounds/history')
        assert hist.status_code==200
        assert hist.json()['items'][0]['id']=='r1'
        assert client.get('/').status_code==200
        assert 'AI' in client.get('/').text
        assert client.get('/live.js').status_code==200


def test_recommendation_note_and_cross_origin_block(app):
    with TestClient(app) as client:
        r=client.put('/v1/rounds/r1/note',json={'text':'難しい猫の画像が有効と考える'})
        assert r.status_code==200
        assert client.get('/v1/rounds/r1/picks/me').json()['note']=='難しい猫の画像が有効と考える'
        assert client.put('/v1/rounds/r1/picks/3',headers={'Origin':'https://evil.example'}).status_code==403
        assert client.get('/v1/samples/3/image').status_code==403
        assert client.get('/v1/samples/3').status_code==200
        assert client.get('/v1/samples/999').status_code==404
