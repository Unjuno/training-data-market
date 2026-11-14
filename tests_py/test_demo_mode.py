"""Demo must run without external CIFAR files, and never claim CIFAR measurements."""
from fastapi.testclient import TestClient
from backend import ml
from backend.service import make_app
from backend.store import GameStore


def test_procedural_demo_full_round(tmp_path, monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*64)
    monkeypatch.setenv('TDM_ADMIN_KEY','k'*40)
    monkeypatch.setenv('TDM_DEMO_MODE','true')
    monkeypatch.setenv('TDM_PUBLISH_IMAGES','false')
    prepared=ml.prepare_demo(tmp_path)
    assert prepared['dataset']=='SYNTHETIC_PIXEL_ART'
    import json
    manifest=json.loads((tmp_path/'manifest.json').read_text())
    parts=manifest['splits']
    assert {k:len(v) for k,v in parts.items()}=={'initial':200,'public':100,'safety':100,'candidate':1000,'test':200}
    flat=[i for values in parts.values() for i in values]
    assert len(flat)==len(set(flat))==1600
    db=GameStore(tmp_path/'votes.sqlite3')
    with TestClient(make_app(db,tmp_path)) as client:
        current=client.get('/v1/rounds/current').json()
        assert current['mode']=='DEMO'
        assert current['dataset_name']=='SYNTHETIC_PIXEL_ART'
        samples=client.get('/v1/samples?limit=1').json()
        assert samples['items'][0]['image_url']
        assert 'image/png' in client.get(samples['items'][0]['image_url']).headers['content-type']
        first=samples['items'][0]['id']
        assert client.put(f'/v1/rounds/round-0001/picks/{first}').status_code==200
        assert client.post('/v1/admin/rounds/round-0001/lock',headers={'X-Admin-Key':'k'*40}).status_code==200
        result=ml.run_locked_round(tmp_path,tmp_path,'round-0001')
        assert result['community_steps']==result['random_steps']==40
        assert client.get('/v1/rounds/current').json()['round']['id']=='round-0002'
