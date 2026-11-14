import pytest
from backend.store import GameStore, GameError

@pytest.fixture
def store(tmp_path):
    s=GameStore(tmp_path/'db.sqlite3');s.initialize()
    s.bootstrap_samples([(i,i%10) for i in range(200)], version='fixture-v1')
    s.open_round(round_id='r1',checkpoint='cp0',targets=(3,5),seed=123)
    return s


def test_multiuser_votes_idempotence_and_cap(store):
    for i in range(10):assert store.set_pick('r1','user_a',i) in ('created','exists')
    assert store.set_pick('r1','user_a',0)=='exists'
    with pytest.raises(GameError) as e:store.set_pick('r1','user_a',10)
    assert e.value.status_code==409
    assert len(store.get_picks('r1','user_a'))==10
    assert store.set_pick('r1','user_b',10)=='created'
    assert store.get_counts('r1')[10]==1
    assert store.delete_pick('r1','user_a',0) is True
    assert store.set_pick('r1','user_a',10)=='created'


def test_votes_locked_and_candidate_membership_enforced(store):
    with pytest.raises(GameError) as e:store.set_pick('r1','user_a',999)
    assert e.value.status_code==404
    store.lock_round('r1')
    with pytest.raises(GameError) as e:store.set_pick('r1','user_a',1)
    assert e.value.status_code==409
    with pytest.raises(GameError) as e:store.delete_pick('r1','user_a',1)
    assert e.value.status_code==409
    with pytest.raises(GameError):store.lock_round('r1')


def test_round_snapshot_is_persistent(tmp_path,store):
    store.set_pick('r1','a',4)
    store.set_pick('r1','b',4)
    store.lock_round('r1')
    reopened=GameStore(tmp_path/'db.sqlite3')
    assert reopened.get_round('r1')['status']=='LOCKED'
    assert reopened.get_counts('r1')[4]==2


def test_finalize_opens_next_round_and_freezes_consumed_images(store):
    store.set_pick('r1','participant',4)
    store.lock_round('r1')
    store.finalize_round('r1',result_json='{"winner":"community"}',
                         next_round_id='r2',next_checkpoint='cp1',
                         next_targets=(1,9),next_seed=124,consumed_ids=[4,15])
    assert store.get_round('r1')['status']=='PUBLISHED'
    assert store.get_round('r2')['status']=='OPEN'
    assert 4 not in store.get_classes() and 15 not in store.get_classes()
    assert store.get_counts('r1')[4]==1
    with pytest.raises(GameError):
        store.finalize_round('r1','{}','r2','cp1',(1,9),124,[])
    with pytest.raises(GameError):store.set_pick('r2','participant',4)


def test_notes_are_round_bound_and_locked(store):
    assert store.set_note('r1','alice','この難例は猫と犬の識別に役立つ')=='saved'
    assert store.get_note('r1','alice')=='この難例は猫と犬の識別に役立つ'
    with pytest.raises(GameError) as ex:store.set_note('r1','alice','x'*401)
    assert ex.value.status_code==422
    store.lock_round('r1')
    with pytest.raises(GameError):store.set_note('r1','alice','変更できない')
