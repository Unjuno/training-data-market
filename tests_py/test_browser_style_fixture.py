"""The browser smoke must render the same stylesheet stack as the live page."""
from tests_e2e.ux_flow import markup


def test_browser_fixture_loads_game_and_personal_result_styles():
    html=markup()
    assert '.result-scorecards{' in html
    assert '.personal-participation:not([hidden])' in html
