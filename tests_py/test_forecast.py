import json
import pytest
from backend.forecast import judge_round, forecast_points
from backend.store import GameStore, GameError


def result(com=0.54, rnd=0.57, votes=True):
    return {"has_votes": votes, "community": {"target_loss": com}, "random": {"target_loss": rnd}, "promotion": "rollback"}


def test_round_judgement_never_confuses_promotion_with_winner():
    assert judge_round(result())['outcome'] == 'community'
    assert judge_round(result(0.62, 0.56))['outcome'] == 'random'
    assert judge_round(result(0.5405, 0.54))['outcome'] == 'tie'
    assert judge_round(result(votes=False))['outcome'] == 'unscored'
    assert judge_round({"has_votes": True, "community": {}, "random": {}})['outcome'] == 'unscored'
    assert judge_round(result(float('nan'), 0.55))['outcome'] == 'unscored'


def test_points_are_quadratic_and_do_not_reward_ties():
    assert forecast_points(75, 'community') == 94  # round(93.75)
    assert forecast_points(75, 'random') == 44  # round(43.75)
    assert forecast_points(50, 'community') == 75
    assert forecast_points(95, 'tie') is None
    with pytest.raises(ValueError): forecast_points(101, 'community')
    with pytest.raises(ValueError): forecast_points(True, 'community')
    with pytest.raises(ValueError): forecast_points(53, 'random')


@pytest.fixture
def store(tmp_path):
    db = GameStore(tmp_path / 'votes.sqlite3')
    db.initialize()
    db.bootstrap_samples([(i, i % 10) for i in range(220)], 'synthetic')
    db.open_round('r1', 'cp0', (3, 5), 8)
    return db


def test_forecast_persists_and_is_editable_only_before_deadline(store):
    assert store.get_forecast('r1', 'alice') is None
    assert store.set_forecast('r1', 'alice', 65) == 'created'
    assert store.set_forecast('r1', 'alice', 80) == 'updated'
    assert store.get_forecast('r1', 'alice') == 80
    for invalid in [0, 100, 63, True, -5, '70']:
        with pytest.raises(GameError) as e: store.set_forecast('r1', 'alice', invalid)
        assert e.value.status_code == 422
    store.lock_round('r1')
    with pytest.raises(GameError) as e: store.set_forecast('r1', 'alice', 75)
    assert e.value.status_code == 409
    assert store.get_forecast('r1', 'alice') == 80


def test_personal_history_scores_immutable_round_and_ignores_missing_votes(store):
    store.set_forecast('r1', 'alice', 75)
    store.set_forecast('r1', 'bob', 25)
    store.lock_round('r1')
    store.publish_result('r1', json.dumps(result()))
    history = store.player_history('alice')
    assert history['total_points'] == 94
    assert history['scored_rounds'] == 1
    assert history['items'][0]['outcome'] == 'community'
    assert history['items'][0]['forecast_pct'] == 75
    assert store.player_history('bob')['total_points'] == 44
    assert store.player_history('missing')['total_points'] == 0
    # Published outcome cannot be changed by the user or another voting round.
    with pytest.raises(GameError): store.set_forecast('r1','alice',5)


def test_old_database_initialize_adds_forecast_without_changing_existing_votes(tmp_path):
    db = GameStore(tmp_path / 'old.sqlite3')
    db.initialize()
    db.bootstrap_samples([(i, i % 10) for i in range(220)], 'synthetic')
    db.open_round('r1', 'cp0', (3, 5), 8)
    db.set_pick('r1','alice',12)
    db.initialize()
    assert db.get_picks('r1','alice') == [12]
    db.set_forecast('r1','alice',60)
    assert db.get_forecast('r1','alice')==60

def test_cumulative_points_include_all_rounds_not_just_recent_history(store):
    # 23 scored rounds, but the history preview defaults to only the latest 20.
    for n in range(1,24):
        round_id=f'r{n}'
        if n>1:
            store.open_round(round_id,'cp0',(3,5),8)
        store.set_forecast(round_id,'alice',50)
        store.lock_round(round_id)
        store.publish_result(round_id,json.dumps(result()))
    value=store.player_history('alice')
    assert len(value['items'])==20
    assert value['scored_rounds']==23
    assert value['total_points']==23*75
