"""Regression coverage for time-based, exactly-one-owner batch processing."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.store import GameError, GameStore


def make_store(tmp_path):
    store = GameStore(tmp_path / 'db.sqlite3')
    store.initialize()
    store.bootstrap_samples([(n, n % 10) for n in range(160)], 'fixture')
    store.open_round('round-0001', 'initial', (3, 5), seed=11, duration_seconds=60)
    return store


def test_two_workers_cannot_claim_the_same_batch(tmp_path):
    store = make_store(tmp_path)
    store.set_pick('round-0001', 'alice', 10)
    store.set_pick('round-0001', 'bob', 10)
    store.set_forecast('round-0001', 'alice', 75)
    store.lock_round('round-0001')
    with ThreadPoolExecutor(max_workers=2) as ex:
        attempts = list(ex.map(lambda _: store.claim_round('round-0001'), range(2)))
    winners = [value for value in attempts if value is not None]
    assert len(winners) == 1
    assert len(winners[0]) >= 32
    round_data = store.get_round('round-0001')
    assert round_data['status'] == 'TRAINING'
    assert round_data['worker_token'] == winners[0]
    assert round_data['worker_attempts'] == 1
    assert round_data['locked_at'] is not None
    assert store.vote_summary('round-0001') == {
        'vote_count': 2, 'voter_count': 2, 'forecast_count': 1, 'frozen': True,
    }


def test_training_batch_needs_matching_owner_token_to_finalize(tmp_path):
    store = make_store(tmp_path)
    store.lock_round('round-0001')
    token = store.claim_round('round-0001')
    with pytest.raises(GameError) as error:
        store.finalize_round('round-0001', '{}', 'round-0002', 'cp1', (3, 5), 12, [], claim_token='not-owner')
    assert error.value.status_code == 409
    assert store.get_round('round-0001')['status'] == 'TRAINING'
    store.finalize_round('round-0001', '{}', 'round-0002', 'cp1', (3, 5), 12, [], claim_token=token)
    assert store.get_round('round-0001')['status'] == 'PUBLISHED'
    assert store.get_round('round-0002')['status'] == 'OPEN'
    assert store.claim_round('round-0001') is None


def test_failed_batch_requires_explicit_operator_recovery(tmp_path):
    store = make_store(tmp_path)
    store.lock_round('round-0001')
    old_token = store.claim_round('round-0001')
    assert store.claim_round('round-0001') is None
    with pytest.raises(GameError):
        store.recover_training_round('round-0001', expected_token='incorrect')
    store.recover_training_round('round-0001', expected_token=old_token)
    assert store.get_round('round-0001')['status'] == 'LOCKED'
    new_token = store.claim_round('round-0001')
    assert new_token != old_token
    with pytest.raises(GameError):
        store.finalize_round('round-0001', '{}', 'round-0002', 'cp1', (3, 5), 12, [], claim_token=old_token)
    assert store.get_round('round-0001')['worker_attempts'] == 2


def test_old_direct_publish_cannot_bypass_batch_training(tmp_path):
    store=make_store(tmp_path)
    store.lock_round('round-0001')
    with pytest.raises(GameError) as exc:
        store.publish_result('round-0001','{"fake":"ready"}')
    assert exc.value.status_code == 409
    assert store.get_round('round-0001')['status']=='LOCKED'
