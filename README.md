# Job automation for EC2

Python/FastAPI service: Greenhouse, Lever and Ashby job collection; configurable title/location filters; keyword scoring; truthful resume PDFs; configurable Playwright application forms; SQLite history and Excel export with an Activity sheet. The worker runs at startup and periodically. Run one service instance with one Uvicorn worker.

## What is automated

The service is deliberately split into an automated, repeatable pipeline with guardrails around anything that could submit an application:

- **Job-board collection:** pulls live listings from the Greenhouse, Lever, and Ashby public job-board APIs for the company boards listed in `config.json`.
- **Scheduled refreshes:** starts a collection cycle when the API starts, then repeats at the configurable `interval_minutes` cadence (minimum five minutes). A manual `POST /run` or `jobbot-local.ps1 run` starts a cycle on demand.
- **Filtering:** removes listings outside the configured role titles, locations, excluded titles, or maximum explicitly required years of experience.
- **Relevance scoring:** scores retained listings against skills in the verified profile and only prepares jobs at or above `minimum_score`.
- **Truthful resume preparation:** generates a job-specific PDF by reordering existing skills and verified experience bullets for relevance; it never invents or rewrites claims.
- **Application queue and audit trail:** persists jobs, statuses, timestamps, notes, and collection/application events in SQLite, so repeated runs update the same job rather than duplicating it.
- **Excel reporting:** regenerates `jobs.xlsx` on every cycle with a Jobs sheet and an Activity sheet, ready to download through `/excel` or `jobbot-local.ps1 excel`.
- **Optional guarded form automation:** when explicitly enabled, Playwright can fill tested, host-specific, single-page HTTPS application forms, upload the prepared resume, submit, and verify a confirmation selector.
- **Submission safeguards:** auto-submit is off by default; each host needs a tested adapter, requests are restricted to approved hosts, CAPTCHA and unsupported flows pause for review, screenshots are saved before/after submission, and a daily attempt limit is enforced. Interrupted or unconfirmed submissions are marked uncertain and are never automatically retried.
- **Protected local/EC2 operation:** the API requires a bearer token and binds to loopback only. Docker uses a persistent volume for job history, PDFs, screenshots, and exports.

This is not a scraper for every job on the internet or a universal application bot. It automates the specified boards and only automates applications for forms whose exact adapter has been tested.

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

Add real target company boards, using the company slug in its careers URL:

```json
"boards": [
  {"source": "greenhouse", "slug": "YOUR_COMPANY_BOARD", "company": "Company name"},
  {"source": "lever", "slug": "YOUR_COMPANY_BOARD"},
  {"source": "ashby", "slug": "YOUR_COMPANY_BOARD"}
]
```

Boards are deliberately empty in the example. This collects specified companies, not all jobs on the internet. Location matching is substring matching on the source location; remote eligibility and work authorization need your review. Scores are keyword relevance, not ATS scores or eligibility guarantees. It refreshes available listings but does not yet mark disappeared jobs as closed.

`max_required_years` rejects postings whose descriptions explicitly require more experience than the configured value. It is a conservative text rule, so read every prepared job before applying.

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
