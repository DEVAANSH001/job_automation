import logging
from typing import Dict, Any, Iterator
import httpx

from jobbot.scrapers.base import normalize_job

logger = logging.getLogger(__name__)


def collect_remoteok(limit: int = 30) -> Iterator[Dict[str, Any]]:
    """Fetch recent tech openings from RemoteOK public JSON endpoint."""
    url = "https://remoteok.com/api"
    headers = {"User-Agent": "JobBot/1.0 (Job Aggregation Automation)"}
    try:
        with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return
            data = resp.json()
            # First element is usually legal disclaimer/metadata
            items = data[1:] if len(data) > 1 and isinstance(data[0], dict) and "legal" in data[0] else data
            count = 0
            for item in items:
                if not isinstance(item, dict) or not item.get("position"):
                    continue
                title = item.get("position", "")
                company = item.get("company", "RemoteOK Company")
                location = item.get("location") or "Remote"
                job_url = item.get("url") or f"https://remoteok.com/remote-jobs/{item.get('id', '')}"
                description = item.get("description", "")
                tags = " ".join(item.get("tags", []))
                full_desc = f"{description}\nTags: {tags}"

                yield normalize_job(
                    source="feed:remoteok",
                    company=company,
                    title=title,
                    location=location,
                    url=job_url,
                    description=full_desc,
                    unique_key=str(item.get("id") or job_url),
                )
                count += 1
                if count >= limit:
                    break
    except Exception as exc:
        logger.warning(f"RemoteOK feed collection failed: {exc}")


def collect_arbeitnow(limit: int = 30) -> Iterator[Dict[str, Any]]:
    """Fetch tech openings from Arbeitnow public JSON endpoint."""
    url = "https://www.arbeitnow.com/api/job-board-api"
    headers = {"User-Agent": "JobBot/1.0"}
    try:
        with httpx.Client(timeout=20, headers=headers, follow_redirects=True) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return
            data = resp.json()
            items = data.get("data", [])
            count = 0
            for item in items:
                title = item.get("title", "")
                company = item.get("company_name", "Company")
                location = item.get("location", "Remote")
                job_url = item.get("url", "")
                description = item.get("description", "")
                remote = "Remote" if item.get("remote") else location

                if not title or not job_url:
                    continue

                yield normalize_job(
                    source="feed:arbeitnow",
                    company=company,
                    title=title,
                    location=remote,
                    url=job_url,
                    description=description,
                    unique_key=item.get("slug") or job_url,
                )
                count += 1
                if count >= limit:
                    break
    except Exception as exc:
        logger.warning(f"Arbeitnow feed collection failed: {exc}")


def collect_tech_feeds(cfg: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Collect from enabled public tech feeds."""
    scrapers_cfg = cfg.get("scrapers", {})
    feeds_cfg = scrapers_cfg.get("tech_feeds", {})
    if not feeds_cfg.get("enabled", True):
        return

    sources = feeds_cfg.get("sources", ["remoteok", "arbeitnow"])
    if "remoteok" in sources:
        yield from collect_remoteok()
    if "arbeitnow" in sources:
        yield from collect_arbeitnow()
