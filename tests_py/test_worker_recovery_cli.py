import sys
import pytest
from backend.worker import main
from backend.store import GameStore


def test_operator_can_requeue_batch_only_with_explicit_confirmation(tmp_path, monkeypatch):
    db=GameStore(tmp_path/'votes.sqlite3');db.initialize()
    db.bootstrap_samples([(i,i%10) for i in range(160)],'fixture')
    db.open_round('round-0001','initial',(3,5),21,duration_seconds=60)
    db.lock_round('round-0001');token=db.claim_round('round-0001')
    monkeypatch.setattr(sys,'argv', ['worker','--state-root',str(tmp_path),
                                    '--recover-round','round-0001','--confirm-worker-stopped'])
    main()
    assert db.get_round('round-0001')['status']=='LOCKED'
    assert db.get_round('round-0001')['worker_token'] is None
    assert db.get_round('round-0001')['worker_attempts']==1
