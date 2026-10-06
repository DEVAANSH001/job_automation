import json
import logging
import os
import re
from typing import Dict, Any, Iterator, List
from urllib.parse import urljoin, urlparse

from jobbot.scrapers.base import clean_html, normalize_job

logger = logging.getLogger(__name__)


def extract_with_llm(markdown_content: str, target_name: str, base_url: str) -> List[Dict[str, Any]]:
    """Optional LLM structured extraction if GEMINI_API_KEY or OPENAI_API_KEY is available."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            import httpx
            prompt = (
                f"You are a job extractor. Extract job openings from the following markdown text of {target_name}. "
                "Return a strict JSON list of objects with fields: "
                "title (string), company (string), location (string), url (string relative or absolute), description (string). "
                "Return ONLY the raw JSON array.\n\n"
                f"Content:\n{markdown_content[:12000]}"
            )
            response = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30.0,
            )
            if response.status_code == 200:
                text_res = response.json()["candidates"][0]["content"]["parts"][0]["text"]
                # Clean code fences if present
                clean_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_res.strip(), flags=re.MULTILINE)
                parsed = json.loads(clean_json)
                if isinstance(parsed, list):
                    return parsed
        except Exception as e:
            logger.debug(f"LLM extraction skipped/failed: {e}")

    return []


def extract_jobs_heuristic(page_content: str, base_url: str, default_company: str) -> List[Dict[str, Any]]:
    """Extract job listings heuristically from HTML using BeautifulSoup."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_content, "html.parser")
    jobs = []

    # Common job listing container selectors or anchor patterns
    selectors = [
        "[data-testid*='job']",
        ".job-card",
        ".job-listing",
        ".posting",
        ".opening",
        "li.job",
        "div.job-item",
        "a[href*='/jobs/']",
        "a[href*='/careers/']",
        "a[href*='/posting/']",
    ]

    elements = []
    for sel in selectors:
        found = soup.select(sel)
        if found:
            elements.extend(found)

    # If no specific containers found, inspect anchors with job-related keywords
    if not elements:
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if any(k in href for k in ["/job/", "/jobs/", "/career/", "/careers/", "/position/", "/positions/"]):
                elements.append(a)

    seen_urls = set()
    for el in elements:
        # Find link
        a_tag = el if el.name == "a" else el.find("a", href=True)
        if not a_tag or not a_tag.get("href"):
            continue

        raw_url = a_tag["href"]
        full_url = urljoin(base_url, raw_url)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Title extraction
        title_el = el.find(["h2", "h3", "h4", "h5", "strong"])
        title = title_el.get_text(strip=True) if title_el else a_tag.get_text(strip=True)
        if not title or len(title) > 100 or len(title) < 3:
            continue

        # Location extraction
        loc_el = el.find(class_=re.compile(r"location|city|country|workplace", re.I))
        location = loc_el.get_text(strip=True) if loc_el else "Remote / Unspecified"

        # Company extraction
        comp_el = el.find(class_=re.compile(r"company|org", re.I))
        company = comp_el.get_text(strip=True) if comp_el else default_company

        desc = clean_html(el.get_text(separator=" ", strip=True))

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": full_url,
            "description": desc or title,
        })

    return jobs


def collect_ai_scrapers(cfg: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Scrape dynamic career portals and startup hubs using Playwright."""
    scrapers_cfg = cfg.get("scrapers", {})
    ai_cfg = scrapers_cfg.get("ai_scrapers", {})
    if not ai_cfg.get("enabled", True):
        return

    targets = ai_cfg.get("targets", [])
    if not targets:
        return

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright not installed, skipping AI scrapers.")
        return

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for target in targets:
                name = target.get("name", "career_portal")
                url = target.get("url", "")
                if not url:
                    continue

                try:
                    logger.info(f"AI Scraper launching for target '{name}': {url}")
                    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                    page = context.new_page()
                    page.set_default_timeout(30000)
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)  # Allow client-side rendering / React / hydration

                    content = page.content()
                    default_company = target.get("company", name)

                    # Try LLM extraction if enabled, otherwise fallback to DOM heuristic
                    extracted = []
                    from markdownify import markdownify as md
                    page_md = md(content)
                    extracted = extract_with_llm(page_md, name, url)

                    if not extracted:
                        extracted = extract_jobs_heuristic(content, url, default_company)

                    for item in extracted:
                        item_url = urljoin(url, item.get("url", ""))
                        yield normalize_job(
                            source=f"ai_scraper:{name.lower().replace(' ', '_')}",
                            company=item.get("company", default_company),
                            title=item.get("title", ""),
                            location=item.get("location", "Remote"),
                            url=item_url,
                            description=item.get("description", ""),
                        )
                    context.close()
                except Exception as exc:
                    logger.warning(f"AI scraper failed for '{name}': {exc}")
                    continue
        finally:
            browser.close()
