# Job automation for EC2 & Local

Python/FastAPI service: Multi-source AI job scrapers (JobSpy across LinkedIn, Indeed, Glassdoor, ZipRecruiter; Playwright AI web scrapers; RemoteOK/Arbeitnow feeds; and Greenhouse, Lever, Ashby ATS APIs); resume-first query generation and multi-factor relevance scoring; truthful tailored resume PDFs; configurable Playwright application forms; SQLite history and Excel export with an Activity sheet. The worker runs at startup and periodically.

## What is automated

The service runs an automated, repeatable pipeline with guardrails around anything that could submit an application:

- **Multi-source AI job collection:**
  - **JobSpy aggregator:** scrapes live openings across **LinkedIn**, **Indeed**, **Glassdoor**, and **ZipRecruiter** using resume-derived queries and location preferences.
  - **Playwright AI web scrapers:** scrapes dynamic JavaScript-rendered career portals and startup hubs with DOM heuristic extraction and optional Gemini/LLM schema extraction.
  - **Live tech feeds:** pulls fresh developer listings from **RemoteOK** and **Arbeitnow**.
  - **ATS board collectors:** collects listings from Greenhouse, Lever, and Ashby public board APIs configured in `config.json`.
- **Resume-first search queries:** automatically synthesizes targeted search queries from your verified profile stack (e.g., target roles, tech stack combinations like Python/FastAPI or React/Next.js).
- **Scheduled refreshes:** starts a collection cycle when the API starts, then repeats at the configurable `interval_minutes` cadence (minimum five minutes). A manual `POST /run` or `jobbot-local.ps1 run` starts a cycle on demand.
- **Filtering & guardrails:** removes listings outside the configured role titles, locations, excluded titles, or maximum explicitly required years of experience.
- **Multi-factor resume relevance scoring:** scores listings based on seniority fit (boosting internships/entry-level/fresher roles), core stack synergy against verified skills and project domains, logging match rationales for each job. Only prepares jobs at or above `minimum_score`.
- **Truthful resume preparation:** generates a job-specific PDF by reordering existing skills and verified experience bullets for relevance; it never invents or rewrites claims.
- **Application queue and audit trail:** persists jobs, statuses, timestamps, notes, and collection/application events in SQLite, so repeated runs update the same job rather than duplicating it.
- **Excel reporting:** regenerates `jobs.xlsx` on every cycle with a Jobs sheet and an Activity sheet, ready to download through `/excel` or `jobbot-local.ps1 excel`.
- **Optional guarded form automation:** when explicitly enabled, Playwright can fill tested, host-specific, single-page HTTPS application forms, upload the prepared resume, submit, and verify a confirmation selector.
- **Submission safeguards:** auto-submit is off by default; each host needs a tested adapter, requests are restricted to approved hosts, CAPTCHA and unsupported flows pause for review, screenshots are saved before/after submission, and a daily attempt limit is enforced. Interrupted or unconfirmed submissions are marked uncertain and are never automatically retried.
- **Protected local/EC2 operation:** the API requires a bearer token and binds to loopback only. Docker uses a persistent volume for job history, PDFs, screenshots, and exports.

## Complete build inventory

| Area | What is built |
| --- | --- |
| Service | A Python 3.12 FastAPI service with one in-process asynchronous worker. It runs a cycle at startup and thereafter using `interval_minutes`; a lock prevents overlapping cycles. |
| Job sources | JobSpy (LinkedIn, Indeed, Glassdoor, ZipRecruiter), Playwright AI web scrapers, Tech Feeds (RemoteOK, Arbeitnow), and Greenhouse, Lever, and Ashby public job-board collectors. Each listing receives a stable deterministic 24-character ID so refreshes update rather than duplicate. |
| Selection & Matching | Resume-driven query generator, multi-factor scoring (seniority fit, stack synergy, experience cap, location rules). Existing jobs are re-scored whenever the configuration changes. |
| Resume generator | ReportLab PDF generation from verified profile facts: contact details, links, skills, experience, education, projects, and achievements. Relevant skills and bullets are reordered, while original claims remain unchanged. |
| Application runner | A Playwright/Chromium runner for explicitly tested, host-specific, single-page HTML forms. It supports `fill`, `select`, boolean `check`, and resume `upload` steps. |
| Review workflow | Jobs move through `discovered`, `filtered`, `needs_profile`, `prepared`, `applying`, `applied`, `needs_review`, `submission_uncertain`, and `error` states as appropriate. Unsubmitted review/error jobs can be explicitly re-queued. |
| Data and reports | SQLite database in WAL mode for jobs and events; PDF resumes and application screenshots on disk; formatted Excel workbook with filterable Jobs and Activity sheets. Text is stored as text to prevent formula injection in Excel exports. |
| Local operation | PowerShell setup, startup, status, on-demand run, and Excel-download scripts. The local server only listens on `127.0.0.1`. |
| Deployment | Dockerfile that installs Chromium and its dependencies, plus Compose deployment with loopback-only port publishing, persistent data volume, read-only configuration mount, restart policy, init process, and shared-memory allocation for the browser. |
| Testing | Pytest coverage for multi-source scrapers, resume matcher, deduplication, re-scoring, filters, Excel formula safety, truthful resume PDFs, missing adapters, daily limits, and bearer-token API access. |

### API

Every endpoint requires `Authorization: Bearer <API_TOKEN>` (at least 24 characters).

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Confirm the service is running. |
| `GET /jobs` | Return the stored jobs, ordered by score and discovery time. |
| `POST /run` | Start an immediate collection, scoring, preparation, optional application, and export cycle. |
| `GET /excel` | Download the most recent `jobs.xlsx` report. |
| `POST /jobs/{job_id}/retry` | Re-queue an unsubmitted `needs_profile`, `needs_review`, or `error` job after correction. Applied, applying, and uncertain submissions are intentionally excluded. |

### Included utilities

- `setup-local.ps1` creates the local virtual environment, installs locked dependencies, and creates `config.json` from the safe example when needed.
- `start-local.ps1` validates prerequisites, generates a random local bearer token on first run, and launches Uvicorn.
- `jobbot-local.ps1` provides `status`, `run`, and `excel` commands against the local protected API.
- `seed_boards.py` is an optional development helper that checks a small set of Greenhouse board slugs and writes reachable boards to the local configuration.
- `import_profile.py` is a one-time local helper for importing verified profile information into `config.json`. It is intentionally ignored by Git along with personal configuration and generated data.

### Configuration surface

`config.example.json` documents the supported settings:

- `interval_minutes`, `minimum_score`, `max_required_years`, and `daily_limit`
- `roles`, `locations`, and `exclude_titles`
- target `boards` for Greenhouse, Lever, and Ashby
- verified `profile` fields, experience, education, skills, projects, achievements, and approved form answers
- `auto_submit` and per-host `application_adapters`

Keep `config.json`, `.local-token`, `.env`, local databases, screenshots, generated PDFs, and Excel exports private. They are excluded from version control by `.gitignore`.

## Run locally on Windows

From PowerShell in this folder:

```powershell
.\setup-local.ps1
.\start-local.ps1
```

Keep that window open. In a second PowerShell window use:

```powershell
.\jobbot-local.ps1 status
.\jobbot-local.ps1 run
.\jobbot-local.ps1 excel
```

The last command downloads `jobs.xlsx` into the project folder. The local API binds only to `127.0.0.1`. A random bearer token is generated in `.local-token`; both files are ignored by Git. Stop the service with `Ctrl+C`.

## Configure

Copy `config.example.json` to `config.json`. Fill your profile, roles and locations. Experience objects contain `title`, `company`, `dates`, and `bullets` (list of verified achievements). Education is a list of strings. Resume tailoring reorders existing skills and bullets; it does not train an AI model or invent/rewrite claims.

Configure scrapers and target company boards in `config.json`:

```json
"scrapers": {
  "jobspy": {
    "enabled": true,
    "sites": ["linkedin", "indeed", "glassdoor", "zip_recruiter"],
    "results_per_role": 10,
    "country": "India",
    "hours_old": 72
  },
  "tech_feeds": {
    "enabled": true,
    "sources": ["remoteok", "arbeitnow"]
  },
  "ai_scrapers": {
    "enabled": true,
    "targets": [
      {
        "name": "Target Portal",
        "url": "https://example.com/careers",
        "company": "Example Inc"
      }
    ]
  }
},
"boards": [
  {"source": "greenhouse", "slug": "YOUR_COMPANY_BOARD", "company": "Company name"},
  {"source": "lever", "slug": "YOUR_COMPANY_BOARD"},
  {"source": "ashby", "slug": "YOUR_COMPANY_BOARD"}
]
```

- **JobSpy:** Aggregates live listings from LinkedIn, Indeed, Glassdoor, and ZipRecruiter using targeted queries generated from your target roles and resume skills.
- **AI Web Scrapers:** Crawls custom JavaScript-rendered career pages using Playwright, extracting job cards and metadata.
- **Tech Feeds:** Pulls real-time remote developer opportunities from RemoteOK and Arbeitnow.
- **ATS Boards:** Direct polling for Greenhouse, Lever, and Ashby slugs.

`max_required_years` rejects postings whose descriptions explicitly require more experience than the configured value (ideal for student/new-grad/intern thresholds). Scores are multi-factor relevance evaluations matching seniority fit, core stack, and project keywords against your verified resume.

## EC2 deployment (Ubuntu with Docker Engine and Compose installed)

Upload this project to EC2. In its directory:

```bash
cp config.example.json config.json
# Edit config.json with your profile and company boards.
printf 'API_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
chmod 600 .env config.json
sudo docker compose up -d --build
sudo docker compose logs -f
```

The API listens only on EC2 loopback. Keep port 8000 closed in the security group. Access through SSH forwarding:

```bash
ssh -L 8000:127.0.0.1:8000 ubuntu@YOUR_EC2_IP
```

Use the token from `.env` in a local terminal:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/jobs
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/run
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/excel -o jobs.xlsx
```

Download `/excel` whenever needed; it is a snapshot of the database. Editing the Excel file does not change the queue. Jobs, resumes, application screenshots, and the workbook persist in the Docker volume. Back up that volume; do not use `docker compose down -v` unless you intend to delete it. All logged timestamps and daily limits use UTC. Updating config affects the next scheduled cycle.

After correcting profile or adapter configuration, `POST /jobs/{job_id}/retry` queues an unsubmitted review/error job for the next cycle. Applied, applying, and uncertain submissions cannot be retried through this endpoint.

## Application automation

Auto-submit starts disabled. Enable it only after filling your profile and testing an adapter against the actual application form. There is no universal adapter: different employers have different required/custom fields even on the same ATS. The initial runner handles single-page HTML forms, uploads, text/select/checkbox fields. Multi-page forms, login/OTP, iframe forms, and assessments need additional adapters or manual completion. CAPTCHA pauses the job; it is not bypassed.

Configure each exact HTTPS application hostname in `application_adapters`. Example structure (replace every selector with one verified against the actual form):

```json
"auto_submit": true,
"application_adapters": {
  "careers.example.com": {
    "tested": true,
    "resource_hosts": [],
    "steps": [
      {"action": "fill", "selector": "#name", "profile_key": "name"},
      {"action": "fill", "selector": "#email", "profile_key": "email"},
      {"action": "upload", "selector": "input[type=file]"},
      {"action": "select", "selector": "#authorization", "profile_key": "work_authorization"}
    ],
    "submit_selector": "button[type=submit]",
    "confirmation_selector": "#application-success",
    "blocker_selectors": ["iframe[src*=recaptcha]", "iframe[src*=hcaptcha]"]
  }
}
```

Put approved custom answers under `profile.answers`. Add required resource/API hosts only after checking the site's requests. Requests to unlisted hosts are blocked. Use a confirmation selector unique to actual successful submission. The runner saves screenshots before/after submission, enforces a daily attempt cap, and never automatically retries uncertain submissions or interrupted `applying` jobs. Those statuses need manual reconciliation in the SQLite database. It also does not retry `needs_review` jobs automatically. No real applications have been submitted during development.

## Local development

```bash
python -m venv .venv
# Activate the environment for your operating system.
pip install -r requirements.txt
playwright install chromium
pytest -q
# Set API_TOKEN (24+ characters), then:
uvicorn jobbot.api:app --host 127.0.0.1 --port 8000
```

## References

- https://docs.greenhouse.io/job-board.html
- https://github.com/lever/postings-api
- https://docs.ashbyhq.com/using-the-lightweight-job-posting-api-to-list-openings-on-your-site
- https://playwright.dev/python/docs/input
- https://fastapi.tiangolo.com/deployment/docker/
