from backend.worker import poll_once
from backend.store import GameStore


def test_worker_locks_only_after_deadline(tmp_path,monkeypatch):
    db=GameStore(tmp_path/'db.sqlite3');db.initialize()
    db.bootstrap_samples([(i,i%10) for i in range(140)],'fixture')
    db.open_round('r1','initial',(0,1),123,duration_seconds=60)
    monkeypatch.setattr('backend.worker.run_locked_round',lambda *args:'trained')
    opened=db.get_round('r1')['opened_at']
    assert poll_once(db,tmp_path,tmp_path,round_seconds=60,now=opened+59)=='OPEN'
    assert db.get_round('r1')['status']=='OPEN'
    assert poll_once(db,tmp_path,tmp_path,round_seconds=60,now=opened+61)=='trained'
    assert db.get_round('r1')['status']=='LOCKED'
