import hashlib
import html
import re
from typing import Dict, Any
from markdownify import markdownify as md


def clean_html(value: Any) -> str:
    """Clean HTML or markdown text, stripping tags and normalizing whitespace."""
    if not value:
        return ""
    text = str(value)
    # Convert HTML tags to readable markdown if html tags present
    if "<" in text and ">" in text:
        try:
            text = md(text, strip=["script", "style"])
        except Exception:
            text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_job_id(source: str, company: str, identifier: str) -> str:
    """Generate a deterministic 24-character hex ID for a job."""
    raw = f"{source.strip().lower()}:{company.strip().lower()}:{identifier.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def normalize_job(
    source: str,
    company: str,
    title: str,
    location: str,
    url: str,
    description: str,
    unique_key: str = "",
) -> Dict[str, Any]:
    """Normalize a job into the standard format expected by JobBot."""
    clean_desc = clean_html(description)
    key = unique_key or url or f"{title}:{location}"
    return {
        "id": make_job_id(source, company, key),
        "source": source,
        "company": company.strip() or "Unknown Company",
        "title": title.strip(),
        "location": location.strip() if location else "Remote / Unspecified",
        "url": url.strip(),
        "description": clean_desc,
    }
