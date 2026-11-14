import json
from fastapi.testclient import TestClient
from backend.service import make_app
from backend.store import GameStore


def test_natural_images_require_manifest_rights_approval(tmp_path, monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*64)
    monkeypatch.setenv('TDM_PUBLISH_IMAGES','true')
    monkeypatch.delenv('TDM_DEMO_MODE',raising=False)
    store=GameStore(tmp_path/'votes.sqlite3');store.initialize()
    store.bootstrap_samples([(1,3)],'fixture')
    store.open_round('r1','initial',(3,5),99)
    (tmp_path/'manifest.json').write_text(json.dumps({'dataset':'CIFAR-10'}))
    with TestClient(make_app(store,tmp_path)) as client:
        payload=client.get('/v1/samples?limit=1').json()
        assert payload['image_rights_approved'] is False
        assert payload['items'][0]['image_url'] is None
        assert client.get('/v1/samples/1/image').status_code == 403
    (tmp_path/'manifest.json').write_text(json.dumps({'dataset':'CIFAR-10','image_rights_status':'APPROVED'}))
    with TestClient(make_app(store,tmp_path)) as client:
        payload=client.get('/v1/samples?limit=1').json()
        assert payload['image_rights_approved'] is True
        assert payload['items'][0]['image_url'] == '/v1/samples/1/image'


def test_current_round_exposes_server_clock_and_deadline(tmp_path, monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*64)
    store=GameStore(tmp_path/'votes.sqlite3');store.initialize()
    store.bootstrap_samples([(1,3)],'fixture')
    store.open_round('r1','initial',(3,5),99,duration_seconds=120)
    with TestClient(make_app(store,tmp_path)) as client:
        data=client.get('/v1/rounds/current').json()
        assert isinstance(data['server_time'],(int,float))
        assert data['round']['closes_at']>data['server_time']
        assert data['round']['closes_at']-data['round']['opened_at']==120
