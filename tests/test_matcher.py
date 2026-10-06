from jobbot.matcher import generate_search_queries, score_job


def test_generate_search_queries():
    cfg = {
        "roles": ["Software Engineer Intern", "Backend Developer"],
        "profile": {
            "skills": ["Python", "FastAPI", "React", "Next.js"]
        }
    }
    queries = generate_search_queries(cfg)
    assert "Software Engineer Intern" in queries
    assert "Backend Developer" in queries
    assert "Python FastAPI" in queries
    assert "Next.js Developer" in queries


def test_score_job_filters_senior_roles():
    cfg = {
        "roles": ["Backend Developer"],
        "locations": ["India"],
        "exclude_titles": ["Senior"],
        "profile": {"skills": ["Python"]}
    }
    job = {
        "title": "Senior Backend Developer",
        "location": "India",
        "description": "Python developer role with 5 years experience."
    }
    score, reason = score_job(job, cfg)
    assert score == 0
    assert "Filtered" in reason


def test_score_job_filters_experience_exceeded():
    cfg = {
        "roles": ["Software Engineer"],
        "locations": ["India"],
        "max_required_years": 1,
        "profile": {"skills": ["Python"]}
    }
    job = {
        "title": "Software Engineer",
        "location": "India",
        "description": "Requires 3+ years of experience with Python."
    }
    score, reason = score_job(job, cfg)
    assert score == 0
    assert "Filtered" in reason


def test_score_job_boosts_internship_and_skills():
    cfg = {
        "roles": ["Software Engineer Intern", "Backend Developer"],
        "locations": ["India"],
        "max_required_years": 1,
        "profile": {
            "skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "Redis", "AWS"]
        }
    }
    job = {
        "title": "Software Engineer Intern",
        "location": "Bengaluru, India",
        "description": "Looking for an intern with knowledge of Python, FastAPI, Docker, and Redis."
    }
    score, reason = score_job(job, cfg)
    assert score >= 80
    assert "Intern/Entry-level match" in reason
    assert "Python" in reason


def test_score_job_allows_remote():
    cfg = {
        "roles": ["Backend Developer"],
        "locations": ["India"],
        "profile": {"skills": ["Python"]}
    }
    job = {
        "title": "Backend Developer",
        "location": "Remote",
        "description": "Python backend role anywhere."
    }
    score, reason = score_job(job, cfg)
    assert score > 0
