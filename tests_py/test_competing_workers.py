"""The timer can trigger more than one worker: only one processes the round."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock, current_thread

from backend.worker import poll_once
from backend.store import GameStore


def test_simultaneous_timer_ticks_do_not_raise_or_train_twice(tmp_path,monkeypatch):
    store=GameStore(tmp_path/'db.sqlite3');store.initialize()
    store.bootstrap_samples([(i,i%10) for i in range(140)],'fixture')
    store.open_round('round-0001','initial',(3,5),seed=100,duration_seconds=60)
    due=store.get_round('round-0001')['closes_at']
    gate=Barrier(2)
    seen_lock=Lock();seen={'n':0}
    original=store.current_round
    def coordinated_read():
        out=original()
        with seen_lock:
            seen['n']+=1
            count=seen['n']
        if count<=2:gate.wait(timeout=8)
        return out
    monkeypatch.setattr(store,'current_round',coordinated_read)
    called=[]
    def fake_run(*args):
        called.append(args[2])
        return 'trained'
    monkeypatch.setattr('backend.worker.run_locked_round',fake_run)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:poll_once(store,tmp_path,tmp_path,now=due+1),[0,1]))
    assert results.count('trained')==1
    assert sorted(results)==['TRAINING','trained']
    assert called==['round-0001']
    assert store.get_round('round-0001')['status']=='TRAINING'
