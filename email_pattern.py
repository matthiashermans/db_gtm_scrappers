"""Discover email patterns for a company domain and generate emails."""

import re
from utils import google_search, fetch, normalize_name
from bs4 import BeautifulSoup

# Email pattern templates
PATTERNS = {
    "first.last":  lambda f, l, d: f"{f}.{l}@{d}",
    "firstlast":   lambda f, l, d: f"{f}{l}@{d}",
    "first_last":  lambda f, l, d: f"{f}_{l}@{d}",
    "flast":       lambda f, l, d: f"{f[0]}{l}@{d}",
    "f.last":      lambda f, l, d: f"{f[0]}.{l}@{d}",
    "first":       lambda f, l, d: f"{f}@{d}",
    "firstl":      lambda f, l, d: f"{f}{l[0]}@{d}",
    "first.l":     lambda f, l, d: f"{f}.{l[0]}@{d}",
    "last.first":  lambda f, l, d: f"{l}.{f}@{d}",
    "lastfirst":   lambda f, l, d: f"{l}{f}@{d}",
    "last_first":  lambda f, l, d: f"{l}_{f}@{d}",
    "lfirst":      lambda f, l, d: f"{l[0]}{f}@{d}",
    "l.first":     lambda f, l, d: f"{l[0]}.{f}@{d}",
    "last":        lambda f, l, d: f"{l}@{d}",
    "f_last":      lambda f, l, d: f"{f[0]}_{l}@{d}",
    "flast":       lambda f, l, d: f"{f[0]}{l}@{d}",
}


def _extract_emails_from_text(text, domain):
    """Extract email addresses for a specific domain from text."""
    pattern = r'[\w.+-]+@' + re.escape(domain)
    return list(set(re.findall(pattern, text.lower())))


def _infer_pattern_from_email(email, domain):
    """Try to figure out which pattern an email follows.

    Returns pattern name or None.
    """
    local = email.split('@')[0].lower()
    # We can't infer without knowing the person's name,
    # but we can detect the format structure
    if '.' in local:
        parts = local.split('.')
        if len(parts) == 2:
            if len(parts[0]) == 1:
                return "f.last"
            if len(parts[1]) == 1:
                return "first.l"
            return "first.last"  # Most likely
    if '_' in local:
        parts = local.split('_')
        if len(parts) == 2:
            if len(parts[0]) == 1:
                return "f_last"
            return "first_last"
    # No separator
    if len(local) <= 15:
        return "firstlast"  # Best guess for no-separator format
    return None


def _search_email_format_sites(domain, session):
    """Search email format aggregator sites for the domain's email pattern."""
    queries = [
        f'"{domain}" email format',
        f'"{domain}" email pattern',
    ]

    for query in queries:
        results = google_search(query, session, num_results=5)
        for r in results:
            text = (r["title"] + " " + r["snippet"]).lower()

            # Look for explicit pattern mentions
            pattern_mentions = {
                "first.last": ["first.last", "firstname.lastname", "first.lastname"],
                "flast": ["flast", "firstinitiallastname"],
                "f.last": ["f.last", "firstinitial.lastname", "f.lastname"],
                "firstlast": ["firstlast", "firstnamelastname"],
                "first_last": ["first_last", "firstname_lastname"],
                "first": ["firstname@"],
                "last.first": ["last.first", "lastname.firstname"],
                "firstl": ["firstl", "firstnamelastinitial"],
            }

            for pattern_name, indicators in pattern_mentions.items():
                for indicator in indicators:
                    if indicator in text:
                        return pattern_name

            # Look for example emails in the text
            emails = _extract_emails_from_text(r["snippet"], domain)
            if emails:
                pattern = _infer_pattern_from_email(emails[0], domain)
                if pattern:
                    return pattern

    return None


def _search_for_domain_emails(domain, session):
    """Search Google for actual email addresses at this domain."""
    query = f'"@{domain}"'
    results = google_search(query, session, num_results=10)

    all_emails = []
    for r in results:
        text = r["title"] + " " + r["snippet"]
        emails = _extract_emails_from_text(text, domain)
        all_emails.extend(emails)

    # Filter out generic emails
    generic = {"info", "support", "contact", "hello", "admin", "sales",
               "help", "team", "office", "hr", "careers", "jobs",
               "press", "media", "marketing", "noreply", "no-reply"}
    personal_emails = [e for e in all_emails if e.split('@')[0] not in generic]

    if personal_emails:
        pattern = _infer_pattern_from_email(personal_emails[0], domain)
        if pattern:
            return pattern

    return None


def _scrape_company_website(domain, session):
    """Try to find emails on the company's website."""
    pages = [
        f"https://{domain}/contact",
        f"https://{domain}/about",
        f"https://{domain}/team",
        f"https://{domain}/about-us",
        f"https://{domain}/contact-us",
    ]

    for page_url in pages:
        resp = fetch(page_url, session, min_delay=1, max_delay=2)
        if resp and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            text = soup.get_text()

            emails = _extract_emails_from_text(text, domain)
            # Also check mailto links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "mailto:" in href:
                    email = href.replace("mailto:", "").split("?")[0].strip().lower()
                    if domain in email:
                        emails.append(email)

            generic = {"info", "support", "contact", "hello", "admin", "sales",
                       "help", "team", "office", "hr", "noreply"}
            personal = [e for e in emails if e.split('@')[0] not in generic]

            if personal:
                pattern = _infer_pattern_from_email(personal[0], domain)
                if pattern:
                    return pattern

    return None


def discover_email_pattern(domain, session):
    """Discover the email naming pattern for a company domain.

    Returns the pattern name (e.g., 'first.last', 'f.last').
    """
    print(f"  Discovering email pattern for {domain}...")

    # Method 1: Email format aggregator sites
    pattern = _search_email_format_sites(domain, session)
    if pattern:
        print(f"    Found pattern from format sites: {pattern}")
        return pattern

    # Method 2: Search for actual emails at the domain
    pattern = _search_for_domain_emails(domain, session)
    if pattern:
        print(f"    Found pattern from email search: {pattern}")
        return pattern

    # Method 3: Scrape the company website
    pattern = _scrape_company_website(domain, session)
    if pattern:
        print(f"    Found pattern from website: {pattern}")
        return pattern

    # Fallback: most common corporate email pattern
    print(f"    No pattern found, defaulting to first.last")
    return "first.last"


def generate_email(first_name, last_name, domain, pattern):
    """Generate an email address from a name using the discovered pattern."""
    first = normalize_name(first_name)
    last = normalize_name(last_name)

    if not first or not last:
        return ""

    template = PATTERNS.get(pattern)
    if not template:
        # Default to first.last if pattern not recognized
        template = PATTERNS["first.last"]

    return template(first, last, domain)


def format_pattern_display(pattern, domain):
    """Format the pattern for display in the output, e.g. 'first.last@domain.com'."""
    example = PATTERNS.get(pattern, PATTERNS["first.last"])
    return example("first", "last", domain)
