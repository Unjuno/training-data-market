from fastapi.testclient import TestClient
from backend.store import GameStore
from backend.service import make_app


def test_current_round_exposes_only_aggregated_vote_counts(tmp_path,monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*48)
    store=GameStore(tmp_path/'votes.sqlite3')
    store.initialize()
    store.bootstrap_samples([(i,i%10) for i in range(140)],'fixture')
    store.open_round('round-0001','initial',(3,5),11,duration_seconds=90)
    store.set_pick('round-0001','alice',1)
    store.set_pick('round-0001','alice',2)
    store.set_pick('round-0001','bob',2)
    store.set_forecast('round-0001','bob',70)
    with TestClient(make_app(store,tmp_path)) as client:
        info=client.get('/v1/rounds/current').json()
        assert info['vote_summary']=={'vote_count':3,'voter_count':2,'forecast_count':1,'frozen':False}
        assert 'alice' not in str(info) and 'bob' not in str(info)
        store.lock_round('round-0001')
        frozen=client.get('/v1/rounds/current').json()
        assert frozen['vote_summary']['frozen'] is True
        assert frozen['vote_summary']['vote_count'] == 3
