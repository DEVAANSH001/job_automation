from fastapi.testclient import TestClient

from jobbot.api import app


def test_api_requires_token(monkeypatch, tmp_path):
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('API_TOKEN', 'a' * 32)
    client = TestClient(app)
    assert client.get('/jobs').status_code == 401
    assert client.get('/jobs', headers={'Authorization': 'Bearer ' + 'a' * 32}).status_code == 200
    assert client.post('/jobs/missing/retry', headers={'Authorization': 'Bearer ' + 'a' * 32}).status_code == 404
