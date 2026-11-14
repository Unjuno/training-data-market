"""Rollback must not rewrite metrics for an existing, immutable checkpoint."""
from backend import ml
from backend.service import make_app
from backend.store import GameStore
from fastapi.testclient import TestClient


def test_rollback_preserves_baseline_metrics_and_new_round_has_scoped_metrics(tmp_path,monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','x'*64)
    monkeypatch.setenv('TDM_DEMO_MODE','true')
    ml.prepare_demo(tmp_path)
    baseline=(tmp_path/'metrics'/'initial.json').read_bytes()
    store=GameStore(tmp_path/'votes.sqlite3')
    store.lock_round('round-0001')
    monkeypatch.setattr(ml,'select_promotion',lambda *args:'rollback')
    result=ml.run_locked_round(tmp_path,tmp_path,'round-0001')
    assert result['promotion']=='rollback'
    assert (tmp_path/'metrics'/'initial.json').read_bytes()==baseline
    assert (tmp_path/'metrics'/'round-0002.json').is_file()
    with TestClient(make_app(store,tmp_path)) as client:
        current=client.get('/v1/rounds/current').json()
        assert current['round']['id']=='round-0002'
        assert current['metrics']['target_pair']==list(result['next_target_pair'])
