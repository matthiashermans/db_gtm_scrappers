"""Shared utilities: HTTP session, Google search, name parsing, domain extraction."""

import random
import re
import time
import unicodedata
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

SOCIAL_DOMAINS = {
    "linkedin.com", "twitter.com", "facebook.com", "instagram.com",
    "youtube.com", "github.com", "crunchbase.com", "glassdoor.com",
    "wikipedia.org", "bloomberg.com", "reuters.com", "google.com",
    "bing.com", "yahoo.com", "reddit.com",
}


def create_session():
    """Create a requests session with realistic headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return session


def fetch(url, session, min_delay=2.0, max_delay=5.0, retries=3):
    """Fetch a URL with rate limiting and retry logic."""
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(min_delay, max_delay))
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                wait = (2 ** attempt) * 5
                print(f"  Rate limited ({resp.status_code}), waiting {wait}s...")
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as e:
            if attempt == retries - 1:
                print(f"  Request failed: {e}")
                return None
            time.sleep(2 ** attempt)
    return None


def google_search(query, session, num_results=10, delay=None):
    """Search Google and return list of {title, url, snippet} dicts."""
    if delay is None:
        delay = random.uniform(3, 6)
    time.sleep(delay)

    params = {"q": query, "num": num_results, "hl": "en"}
    url = "https://www.google.com/search"

    session.headers["User-Agent"] = random.choice(USER_AGENTS)

    try:
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"  Google search returned {resp.status_code}")
            return []
    except requests.RequestException as e:
        print(f"  Google search failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    # Primary parser: standard Google result blocks
    for g in soup.select("div.g"):
        title_el = g.select_one("h3")
        link_el = g.select_one("a[href]")
        snippet_el = g.select_one("div.VwiC3b") or g.select_one("[data-sncf]") or g.select_one(".st")

        if title_el and link_el:
            href = link_el.get("href", "")
            if href.startswith("/url?q="):
                href = unquote(href.split("/url?q=")[1].split("&")[0])
            results.append({
                "title": title_el.get_text(strip=True),
                "url": href,
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            })

    # Fallback parser if primary found nothing
    if not results:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/url?q=" in href:
                clean_url = unquote(href.split("/url?q=")[1].split("&")[0])
                if clean_url.startswith("http"):
                    text = a.get_text(strip=True)
                    if text and len(text) > 5:
                        results.append({
                            "title": text,
                            "url": clean_url,
                            "snippet": "",
                        })

    return results[:num_results]


def parse_name(full_name):
    """Parse a full name into (first_name, last_name)."""
    # Remove common prefixes/suffixes
    name = re.sub(r'\b(Dr|Mr|Mrs|Ms|Prof|Sir|Jr|Sr|III|II|IV|PhD|MBA|CPA)\b\.?', '', full_name, flags=re.IGNORECASE)
    name = re.sub(r'[^\w\s\-]', '', name).strip()
    parts = name.split()
    if len(parts) == 0:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], parts[-1])


def normalize_name(name):
    """Remove accents and special characters from a name."""
    nfkd = unicodedata.normalize('NFKD', name)
    ascii_name = nfkd.encode('ascii', 'ignore').decode('ascii')
    return ascii_name.lower().strip()


def company_to_domain(company_name, session):
    """Find the primary domain for a company via Google search."""
    results = google_search(f'"{company_name}" official website', session, num_results=10)

    domain_counts = {}
    for r in results:
        try:
            parsed = urlparse(r["url"])
            domain = parsed.netloc.lower()
            # Remove www. prefix
            domain = re.sub(r'^www\.', '', domain)
            # Skip social/news domains
            if any(sd in domain for sd in SOCIAL_DOMAINS):
                continue
            if domain:
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        except Exception:
            continue

    if not domain_counts:
        # Fallback: guess from company name
        clean = re.sub(r'[^a-z0-9]', '', company_name.lower())
        return f"{clean}.com"

    # Return most frequent domain
    return max(domain_counts, key=domain_counts.get)
