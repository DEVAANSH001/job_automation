import pandas as pd
from unittest.mock import MagicMock
from jobbot.scrapers.base import clean_html, make_job_id, normalize_job
from jobbot.scrapers.jobspy_scraper import collect_jobspy
from jobbot.scrapers.ai_scraper import extract_jobs_heuristic
from jobbot.scrapers.tech_feeds import collect_remoteok, collect_arbeitnow


def test_clean_html():
    raw = "<p>Join our <strong>engineering</strong> team &amp; build APIs.</p>"
    cleaned = clean_html(raw)
    assert "Join our engineering team & build APIs." in cleaned
    assert "<p>" not in cleaned


def test_make_job_id_deterministic():
    id1 = make_job_id("jobspy:linkedin", "Google", "https://linkedin.com/jobs/123")
    id2 = make_job_id("jobspy:linkedin", "Google", "https://linkedin.com/jobs/123")
    assert id1 == id2
    assert len(id1) == 24


def test_normalize_job():
    job = normalize_job(
        source="jobspy:linkedin",
        company="TechCorp",
        title="Software Engineer Intern",
        location="India",
        url="https://example.com/job/1",
        description="<p>Great Python role</p>",
    )
    assert job["company"] == "TechCorp"
    assert job["title"] == "Software Engineer Intern"
    assert job["description"] == "Great Python role"
    assert len(job["id"]) == 24


def test_collect_jobspy(monkeypatch):
    dummy_df = pd.DataFrame([
        {
            "id": "1001",
            "site": "linkedin",
            "title": "Backend Intern",
            "company": "Startup Inc",
            "location": "Bengaluru",
            "job_url": "https://linkedin.com/jobs/view/1001",
            "job_url_direct": "",
            "description": "Python, FastAPI and Redis",
        }
    ])

    import jobspy
    monkeypatch.setattr(jobspy, "scrape_jobs", lambda **kwargs: dummy_df)

    cfg = {
        "roles": ["Backend Intern"],
        "locations": ["India"],
        "scrapers": {
            "jobspy": {
                "enabled": True,
                "sites": ["linkedin"],
                "results_per_role": 5,
            }
        }
    }

    jobs = list(collect_jobspy(cfg))
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Backend Intern"
    assert jobs[0]["company"] == "Startup Inc"
    assert jobs[0]["source"] == "jobspy:linkedin"


def test_ai_scraper_heuristic_extraction():
    html_page = """
    <html>
        <body>
            <div class="job-card">
                <h3><a href="/jobs/backend-intern">Backend Engineer Intern</a></h3>
                <span class="location">Remote</span>
                <span class="company">Acme Corp</span>
                <p>We are hiring a backend intern who knows Python.</p>
            </div>
        </body>
    </html>
    """
    extracted = extract_jobs_heuristic(html_page, "https://acme.com", "Acme Corp")
    assert len(extracted) == 1
    assert extracted[0]["title"] == "Backend Engineer Intern"
    assert extracted[0]["url"] == "https://acme.com/jobs/backend-intern"
    assert extracted[0]["location"] == "Remote"


def test_tech_feeds_remoteok(monkeypatch):
    mock_data = [
        {"legal": "disclaimer"},
        {
            "id": "999",
            "position": "Python Developer",
            "company": "RemoteDev",
            "location": "Remote",
            "url": "https://remoteok.com/job/999",
            "description": "Full remote Python developer",
            "tags": ["python", "backend"]
        }
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    import httpx
    monkeypatch.setattr(httpx.Client, "get", lambda *args, **kwargs: mock_resp)

    jobs = list(collect_remoteok(limit=5))
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Python Developer"
    assert jobs[0]["source"] == "feed:remoteok"
