from jobbot import core
from jobbot.apply import apply
from test_core import setup


def seed(monkeypatch, tmp_path):
    cfg = setup(monkeypatch, tmp_path)
    job = dict(id='a', source='lever', company='Example', title='Engineer', location='India', url='https://careers.example.com/apply', description='Python')
    monkeypatch.setattr(core, 'collect', lambda board: iter([job]))
    core.run()
    core.update('a', status='prepared')
    return cfg


def test_missing_adapter_pauses(monkeypatch, tmp_path):
    cfg = seed(monkeypatch, tmp_path)
    apply(core.rows()[0], cfg)
    assert core.rows()[0]['status'] == 'needs_review'


def test_daily_limit_prevents_browser_launch(monkeypatch, tmp_path):
    cfg = seed(monkeypatch, tmp_path)
    cfg['daily_limit'] = 1
    cfg['application_adapters'] = {'careers.example.com': {'tested': True, 'submit_selector': '#submit', 'confirmation_selector': '#success'}}
    core.event('other', 'submit_attempt')
    apply(core.rows()[0], cfg)
    assert core.rows()[0]['status'] == 'prepared'
