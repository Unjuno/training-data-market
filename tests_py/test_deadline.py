import sqlite3
import pytest
from backend.store import GameStore, GameError
from backend.worker import poll_once


def make_store(tmp_path, duration=60):
    store = GameStore(tmp_path / 'votes.sqlite3')
    store.initialize()
    store.bootstrap_samples([(i, i % 10) for i in range(256)], 'fixture')
    store.open_round('r1', 'initial', (3, 5), 22, duration_seconds=duration)
    return store


def test_late_votes_and_notes_rejected_even_when_worker_has_not_locked(tmp_path, monkeypatch):
    store = make_store(tmp_path, duration=60)
    store.set_pick('r1', 'alice', 0)
    store.set_note('r1', 'alice', 'before the deadline')
    due = store.get_round('r1')['closes_at']
    monkeypatch.setattr('backend.store.time.time', lambda: due + 0.01)
    assert store.get_round('r1')['status'] == 'OPEN'
    for fn in [lambda: store.set_pick('r1','alice',1),
               lambda: store.delete_pick('r1','alice',0),
               lambda: store.set_note('r1','alice','late')]:
        with pytest.raises(GameError) as exc:
            fn()
        assert exc.value.status_code == 409
    assert store.get_picks('r1','alice') == [0]
    assert store.get_note('r1','alice') == 'before the deadline'


def test_worker_uses_persisted_deadline_not_runtime_option(tmp_path, monkeypatch):
    store = make_store(tmp_path, duration=60)
    due = store.get_round('r1')['closes_at']
    monkeypatch.setattr('backend.worker.run_locked_round', lambda *args: 'trained')
    assert poll_once(store,tmp_path,tmp_path,round_seconds=3,now=due-1) == 'OPEN'
    assert poll_once(store,tmp_path,tmp_path,round_seconds=9999,now=due+1) == 'trained'
    assert store.get_round('r1')['status'] == 'TRAINING'


def test_next_round_keeps_same_duration(tmp_path):
    store=make_store(tmp_path, duration=123)
    before=store.get_round('r1')
    store.lock_round('r1')
    token=store.claim_round('r1')
    store.finalize_round('r1','{"winner":"community"}', 'r2', 'cp1',(1,9),23,[],claim_token=token)
    following=store.get_round('r2')
    assert abs((following['closes_at']-following['opened_at']) - 123) < 0.001
    assert abs((before['closes_at']-before['opened_at']) - 123) < 0.001


def test_legacy_round_schema_is_migrated_without_losing_votes(tmp_path):
    path=tmp_path/'legacy.sqlite3'
    conn=sqlite3.connect(path)
    conn.executescript('''
    CREATE TABLE rounds (id TEXT PRIMARY KEY,checkpoint TEXT NOT NULL,target_a INTEGER NOT NULL,target_b INTEGER NOT NULL,seed INTEGER NOT NULL,status TEXT NOT NULL,opened_at REAL NOT NULL,locked_at REAL,finished_at REAL,result_json TEXT);
    INSERT INTO rounds (id,checkpoint,target_a,target_b,seed,status,opened_at) VALUES ('old','initial',3,5,22,'OPEN',1000.0);
    ''')
    conn.commit();conn.close()
    store=GameStore(path)
    store.initialize()
    migrated=store.get_round('old')
    assert migrated['closes_at'] == 1000.0 + 86400
    assert migrated['status'] == 'OPEN'
