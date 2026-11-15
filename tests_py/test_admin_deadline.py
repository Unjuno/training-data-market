from fastapi.testclient import TestClient
from backend.store import GameStore
from backend.service import make_app


def test_http_admin_cannot_shortcut_timed_voting(tmp_path,monkeypatch):
    monkeypatch.setenv('TDM_COOKIE_SECRET','s'*48)
    monkeypatch.setenv('TDM_ADMIN_KEY','a'*48)
    db=GameStore(tmp_path/'db.sqlite3');db.initialize()
    db.bootstrap_samples([(i,i%10) for i in range(160)],'fixture')
    db.open_round('round-0001','initial',(3,5),42,duration_seconds=60)
    with TestClient(make_app(db,tmp_path)) as client:
        early=client.post('/v1/admin/rounds/round-0001/lock',headers={'X-Admin-Key':'a'*48})
        assert early.status_code==409
        assert db.get_round('round-0001')['status']=='OPEN'
