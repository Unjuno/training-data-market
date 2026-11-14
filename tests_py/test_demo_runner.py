"""Local runner must be explicitly limited to loopback and avoid production secrets."""
import pytest
from backend.local_demo import make_demo_env, require_loopback


def test_demo_runner_rejects_public_host():
    with pytest.raises(ValueError): require_loopback('0.0.0.0')
    with pytest.raises(ValueError): require_loopback('192.168.1.10')
    assert require_loopback('127.0.0.1')=='127.0.0.1'

def test_local_runner_sets_procedural_mode(monkeypatch):
    monkeypatch.delenv('TDM_COOKIE_SECRET',raising=False)
    monkeypatch.delenv('TDM_ADMIN_KEY',raising=False)
    make_demo_env()
    assert len(__import__('os').environ['TDM_COOKIE_SECRET'])>=32
    assert __import__('os').environ['TDM_DEMO_MODE']=='true'
    assert __import__('os').environ['TDM_PUBLISH_IMAGES']=='false'
