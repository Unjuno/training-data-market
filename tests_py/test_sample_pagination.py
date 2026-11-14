"""The public explorer must page at the database, not read 43k cards per request."""

from backend.store import GameStore
import backend.store as store_module


def test_default_explorer_pages_in_sql_not_python(tmp_path, monkeypatch):
    store = GameStore(tmp_path / 'game.sqlite3')
    store.initialize()
    store.bootstrap_samples([(i, i % 10) for i in range(43000)], 'fixture')
    recorded=[]
    original=store_module.sqlite3.connect

    def traced_connect(*args, **kwargs):
        connection=original(*args, **kwargs)
        connection.set_trace_callback(recorded.append)
        return connection

    monkeypatch.setattr(store_module.sqlite3, 'connect', traced_connect)
    page, count=store.samples_page(page=2,limit=48)
    assert count == 43000
    assert [r['id'] for r in page] == list(range(48,96))
    reads=[s.upper() for s in recorded if s.upper().strip().startswith('SELECT') and 'FROM SAMPLES' in s.upper()]
    assert any(' LIMIT ' in s and ' OFFSET ' in s for s in reads), \
        'unfiltered explorer must issue paginated SQL instead of fetching all candidate images'
    assert not any('ORDER BY ID' in s and ' LIMIT ' not in s for s in reads), \
        'unbounded sample query should not be used for the default explorer'


def test_filtered_explorer_retains_order_total_and_search(tmp_path):
    store=GameStore(tmp_path/'game.sqlite3');store.initialize()
    store.bootstrap_samples([(i, i%10) for i in range(200)], 'fixture')
    page, count=store.samples_page(page=1,limit=5,label=4,search='1')
    assert count==11  # ids 14, 104, 114, 124, ..., 194
    assert [r['id'] for r in page]==[14,104,114,124,134]
    page2,count2=store.samples_page(page=2,limit=5,label=4,search='1')
    assert count2==count
    assert [r['id'] for r in page2]==[144,154,164,174,184]


def test_search_treats_sql_wildcard_characters_as_literal(tmp_path):
    store = GameStore(tmp_path / 'game.sqlite3')
    store.initialize()
    store.bootstrap_samples([(i, i%10) for i in range(200)], 'fixture')
    for needle in ('%', '_'):
        rows, count = store.samples_page(page=1, limit=48, search=needle)
        assert count == 0
        assert rows == []
