import logging
from typing import Dict, Any, Iterator
from jobbot.scrapers.base import normalize_job

logger = logging.getLogger(__name__)


def collect_jobspy(cfg: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Scrape jobs using python-jobspy across LinkedIn, Indeed, Glassdoor, etc."""
    scrapers_cfg = cfg.get("scrapers", {})
    jobspy_cfg = scrapers_cfg.get("jobspy", {})
    if not jobspy_cfg.get("enabled", True):
        return

    try:
        from jobspy import scrape_jobs
    except ImportError:
        logger.warning("python-jobspy not installed, skipping JobSpy scraping.")
        return

    sites = jobspy_cfg.get("sites", ["linkedin", "indeed", "glassdoor"])
    results_wanted = int(jobspy_cfg.get("results_per_role", 10))
    country = jobspy_cfg.get("country", "India")
    hours_old = jobspy_cfg.get("hours_old", 72)

    # Use search queries from config or generate from target roles
    roles = cfg.get("roles", ["Software Engineer Intern", "Backend Developer", "Full Stack Developer"])
    locations = cfg.get("locations", ["India", "Remote"])
    # Pick primary search location to keep queries targeted
    primary_location = locations[0] if locations else "India"

    for role in roles:
        try:
            logger.info(f"JobSpy scraping: query='{role}', location='{primary_location}', sites={sites}")
            df = scrape_jobs(
                site_name=sites,
                search_term=role,
                location=primary_location,
                results_wanted=results_wanted,
                country_indeed=country,
                hours_old=hours_old,
            )
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                title = str(row.get("title") or "")
                company = str(row.get("company") or "")
                job_url = str(row.get("job_url_direct") or row.get("job_url") or "")
                location = str(row.get("location") or primary_location)
                description = str(row.get("description") or "")
                site = str(row.get("site") or "jobspy").lower()
                source_id = str(row.get("id") or job_url)

                if not title or not job_url:
                    continue

                yield normalize_job(
                    source=f"jobspy:{site}",
                    company=company,
                    title=title,
                    location=location,
                    url=job_url,
                    description=description,
                    unique_key=source_id,
                )
        except Exception as exc:
            logger.warning(f"JobSpy scrape failed for '{role}': {exc}")
            continue
