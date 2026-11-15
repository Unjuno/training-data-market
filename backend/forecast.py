"""Settles the game's non-monetary forecast from observed experiment results.

This measures group-level *predictive calibration*, not causal value of a
single training image. It never changes training data or model promotion.
"""
from __future__ import annotations
import math

TIE_MARGIN = 0.001  # absolute target cross-entropy difference; declared before forecasts


def judge_round(result: dict | None) -> dict:
    """Return the observed winner; 'tie' and 'unscored' never earn points."""
    if not isinstance(result, dict) or not result.get('has_votes'):
        return {'outcome': 'unscored', 'reason': '投票がない、または実験結果がありません'}
    try:
        community = float(result['community']['target_loss'])
        random = float(result['random']['target_loss'])
    except (KeyError, ValueError, TypeError):
        return {'outcome': 'unscored', 'reason': '評価値を取得できません'}
    if not math.isfinite(community) or not math.isfinite(random):
        return {'outcome': 'unscored', 'reason': '評価値が有限数ではありません'}
    difference = random - community  # positive means community loss is smaller
    if abs(difference) <= TIE_MARGIN:
        return {'outcome': 'tie', 'reason': '対象Lossの差が判定閾値以内です', 'difference': difference}
    return {'outcome': 'community' if difference > 0 else 'random', 'difference': difference}


def forecast_points(percent: int, outcome: str) -> int | None:
    """Quadratic/Brier-complement score in [0,100]; p=50% scores 75."""
    if type(percent) is not int or not 5 <= percent <= 95 or percent % 5:
        raise ValueError('forecast must be an integer multiple of 5 from 5..95')
    if outcome not in ('community', 'random'):
        return None
    observed = 1 if outcome == 'community' else 0
    return round(100 * (1 - (percent / 100 - observed) ** 2))
