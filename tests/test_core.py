import json

from openpyxl import load_workbook

from jobbot import core


def setup(monkeypatch, tmp_path):
    monkeypatch.setenv('DATA_DIR', str(tmp_path / 'data'))
    path = tmp_path / 'config.json'
    cfg = {'boards': [{'source': 'lever', 'slug': 'example'}], 'roles': ['engineer'], 'locations': ['India'], 'minimum_score': 50, 'max_required_years': 2, 'profile': {'skills': ['Python']}}
    path.write_text(json.dumps(cfg))
    monkeypatch.setenv('CONFIG_PATH', str(path))
    return cfg


def test_collection_deduplicates_and_preserves_submission(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    job = dict(id='a', source='lever', company='Example', title='Engineer', location='India', url='https://jobs.lever.co/example/a', description='Python')
    monkeypatch.setattr(core, 'collect', lambda board: iter([job]))
    core.run()
    core.update('a', status='applied', applied=core.now())
    core.run()
    assert len(core.rows()) == 1
    assert core.rows()[0]['status'] == 'applied'


def test_existing_jobs_are_rescored_when_config_changes(monkeypatch, tmp_path):
    cfg = setup(monkeypatch, tmp_path)
    job = dict(id='a', source='lever', company='Example', title='Engineer', location='India', url='https://example.com', description='Python')
    monkeypatch.setattr(core, 'collect', lambda board: iter([job]))
    core.run()
    assert core.rows()[0]['score'] == 100
    cfg['locations'] = ['Canada']
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(cfg))
    monkeypatch.setattr(core, 'collect', lambda board: iter(()))
    core.run()
    assert core.rows()[0]['score'] == 0
    assert core.rows()[0]['status'] == 'filtered'


def test_filters(monkeypatch, tmp_path):
    cfg = setup(monkeypatch, tmp_path)
    assert core.score({'title': 'Engineer', 'location': 'India', 'description': 'Python'}, cfg) == 100
    assert core.score({'title': 'Sales', 'location': 'India', 'description': 'Python'}, cfg) == 0
    assert core.score({'title': 'Engineer', 'location': 'US', 'description': 'Python'}, cfg) == 0
    assert core.score({'title': 'Engineer', 'location': 'India', 'description': 'Requires 4+ years of software engineering experience and Python'}, cfg) == 0
    assert core.score({'title': 'Engineer', 'location': 'India', 'description': 'Requires 4+ years experience with Python'}, cfg) == 0
    assert core.score({'title': 'Engineer', 'location': 'India', 'description': 'Requires 2 years of software engineering experience and Python'}, cfg) == 100


def test_excel_formula_injection(monkeypatch, tmp_path):
    setup(monkeypatch, tmp_path)
    monkeypatch.setattr(core, 'collect', lambda board: iter([dict(id='a', source='lever', company='=HYPERLINK("evil")', title='Engineer', location='India', url='https://example.com', description='Python')]))
    core.run()
    workbook = load_workbook(core.root() / 'jobs.xlsx')
    assert workbook['Jobs']['B2'].data_type == 's'
    assert workbook['Jobs']['B2'].value.startswith('=')


def test_resume_preserves_verified_content(monkeypatch, tmp_path):
    cfg = setup(monkeypatch, tmp_path)
    job = dict(id='a', source='lever', company='Example', title='Engineer', location='India', url='https://example.com', description='Python')
    monkeypatch.setattr(core, 'collect', lambda board: iter([job]))
    core.run()
    cfg['profile'].update(name='Candidate', email='candidate@example.com', experience=[{'title': 'Developer', 'company': 'Employer', 'bullets': ['Built a Python service']}])
    core.prepare(core.rows()[0], cfg)
    assert core.rows()[0]['status'] == 'prepared'
    assert (core.root() / 'resume-a.pdf').read_bytes().startswith(b'%PDF')
