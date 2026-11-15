"""The browser smoke must render the same stylesheet stack as the live page."""
from tests_e2e.ux_flow import markup


def test_browser_fixture_loads_game_and_personal_result_styles():
    html=markup()
    assert '.result-scorecards{' in html
    assert '.personal-participation:not([hidden])' in html


def test_fixture_import_needs_no_browser_automation_dependency():
    """CI installs Python API deps, but not optional Playwright for screenshots."""
    import subprocess, sys
    code = '''
import builtins
old = builtins.__import__
def blocked(name,*args,**kwargs):
    if name.startswith('playwright'):
        raise ModuleNotFoundError('No module named playwright')
    return old(name,*args,**kwargs)
builtins.__import__ = blocked
from tests_e2e.ux_flow import markup
assert '.result-scorecards{' in markup()
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
