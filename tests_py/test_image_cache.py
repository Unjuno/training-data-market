"""Regression: image browsing must not reload the complete CIFAR-10 dataset per card."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Barrier

import torch
from fastapi.testclient import TestClient
from backend.service import make_app
from backend.store import GameStore


def _app_with_approved_images(tmp_path, monkeypatch, constructor):
    import backend.ml as ml
    monkeypatch.setenv('TDM_COOKIE_SECRET', 's' * 64)
    monkeypatch.setenv('TDM_PUBLISH_IMAGES', 'true')
    monkeypatch.delenv('TDM_DEMO_MODE', raising=False)
    monkeypatch.setenv('TDM_DATA_ROOT', str(tmp_path / 'data'))
    (tmp_path / 'manifest.json').write_text(json.dumps({
        'dataset': 'CIFAR-10',
        'image_rights_status': 'APPROVED',
    }), encoding='utf-8')
    store = GameStore(tmp_path / 'votes.sqlite3')
    store.initialize()
    store.bootstrap_samples([(i, i % 10) for i in range(24)], 'test')
    store.open_round('round-0001', 'initial', (3, 5), 42)
    monkeypatch.setattr(ml, 'CombinedCIFAR', constructor)
    return make_app(store, tmp_path)


def test_repeated_image_requests_initialize_one_cifar_dataset(tmp_path, monkeypatch):
    calls = []

    class FakeCIFAR:
        def __init__(self, _root):
            calls.append('load')
        def __getitem__(self, index):
            return torch.zeros(3, 32, 32), index % 10

    app = _app_with_approved_images(tmp_path, monkeypatch, FakeCIFAR)
    with TestClient(app) as client:
        for sample_id in (0, 1, 2, 1, 0):
            response = client.get(f'/v1/samples/{sample_id}/image')
            assert response.status_code == 200
            assert response.headers['content-type'] == 'image/png'
            assert response.content[:8] == b'\x89PNG\r\n\x1a\n'
    assert len(calls) == 1, 'CIFAR-10 must be loaded once per application instance, not once per image'


def test_parallel_first_requests_initialize_once(tmp_path, monkeypatch):
    calls = []
    lock = Lock()
    gate = Barrier(6)

    class FakeCIFAR:
        def __init__(self, _root):
            with lock:
                calls.append('load')
            time.sleep(.1)
        def __getitem__(self, index):
            return torch.zeros(3, 32, 32), index % 10

    app = _app_with_approved_images(tmp_path, monkeypatch, FakeCIFAR)

    def request(index):
        gate.wait(timeout=5)
        with TestClient(app) as client:
            response = client.get(f'/v1/samples/{index}/image')
            return response.status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert list(pool.map(request, range(6))) == [200] * 6
    assert len(calls) == 1, 'a cold parallel image burst should not redundantly reload the CIFAR dataset'
