"""Find executives/leaders at a company by scraping Google search results."""

import re
from utils import google_search, parse_name

TARGET_ROLES = [
    ("Director of Platform", "Director / Head of Platform"),
    ("Head of Platform", "Director / Head of Platform"),
    ("Director of SRE", "Director / Head of SRE"),
    ("Head of SRE", "Director / Head of SRE"),
    ("Director of Site Reliability", "Director / Head of SRE"),
    ("Director of Infrastructure", "Head / Director of Infrastructure"),
    ("Head of Infrastructure", "Head / Director of Infrastructure"),
    ("VP of Engineering", "VP Engineering"),
    ("VP Engineering", "VP Engineering"),
    ("Vice President of Engineering", "VP Engineering"),
    ("CTO", "CTO"),
    ("Chief Technology Officer", "CTO"),
    ("CIO", "CIO"),
    ("Chief Information Officer", "CIO"),
]

# Grouped search queries to reduce total number of Google searches
SEARCH_GROUPS = [
    {
        "query_roles": '"Director of Platform" OR "Head of Platform"',
        "canonical": "Director / Head of Platform",
        "keywords": ["platform"],
    },
    {
        "query_roles": '"Director of SRE" OR "Head of SRE" OR "Site Reliability"',
        "canonical": "Director / Head of SRE",
        "keywords": ["sre", "site reliability"],
    },
    {
        "query_roles": '"Director of Infrastructure" OR "Head of Infrastructure"',
        "canonical": "Head / Director of Infrastructure",
        "keywords": ["infrastructure"],
    },
    {
        "query_roles": '"VP Engineering" OR "VP of Engineering" OR "Vice President of Engineering"',
        "canonical": "VP Engineering",
        "keywords": ["vp", "vice president", "engineering"],
    },
    {
        "query_roles": '"CTO" OR "Chief Technology Officer"',
        "canonical": "CTO",
        "keywords": ["cto", "chief technology"],
    },
    {
        "query_roles": '"CIO" OR "Chief Information Officer"',
        "canonical": "CIO",
        "keywords": ["cio", "chief information"],
    },
]


def _extract_name_from_linkedin_title(title):
    """Extract a person's name from a LinkedIn Google result title.

    Typical formats:
      'John Smith - Director of Platform - Company | LinkedIn'
      'John Smith | LinkedIn'
      'John Smith – CTO at Company'
    """
    # Remove the LinkedIn suffix
    title = re.sub(r'\s*[\|–\-]\s*LinkedIn\s*$', '', title, flags=re.IGNORECASE)

    # Take the first segment before any separator
    parts = re.split(r'\s*[\|–\-]\s*', title)
    if parts:
        candidate = parts[0].strip()
        # Validate it looks like a name (2-4 capitalized words)
        words = candidate.split()
        if 2 <= len(words) <= 5 and all(w[0].isupper() or w in ("de", "van", "von", "di", "el", "al") for w in words if w):
            return candidate
    return None


def _extract_name_from_snippet(snippet, company, role_keywords):
    """Try to extract a person's name from a search snippet."""
    # Pattern: "Name, Role at Company" or "Name is the Role"
    patterns = [
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,?\s*(?:is\s+(?:the\s+)?)?(?:' + '|'.join(role_keywords) + r')',
        r'(?:' + '|'.join(role_keywords) + r').*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
    ]
    for pat in patterns:
        m = re.search(pat, snippet, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            # Filter out common false positives
            if name.lower() not in ("the company", "our team", "the team", "this company"):
                return name
    return None


def _match_role_from_text(text, search_group):
    """Check if text mentions the role we're searching for."""
    text_lower = text.lower()
    for kw in search_group["keywords"]:
        if kw in text_lower:
            return True
    return False


def find_people(company, session):
    """Find people in target leadership roles at the given company.

    Returns a list of dicts: {first_name, last_name, role}
    """
    found = {}  # key: (first_name_lower, last_name_lower), value: {first_name, last_name, role}

    for group in SEARCH_GROUPS:
        print(f"  Searching for {group['canonical']}...")

        # Pass 1: LinkedIn-targeted search
        query = f'site:linkedin.com/in "{company}" {group["query_roles"]}'
        results = google_search(query, session, num_results=5)

        for r in results:
            name = _extract_name_from_linkedin_title(r["title"])
            if not name:
                name = _extract_name_from_snippet(r["snippet"], company, group["keywords"])
            if name:
                first, last = parse_name(name)
                if first and last:
                    key = (first.lower(), last.lower())
                    if key not in found:
                        found[key] = {
                            "first_name": first.title(),
                            "last_name": last.title(),
                            "role": group["canonical"],
                        }
                        print(f"    Found: {first.title()} {last.title()} - {group['canonical']}")

        # Pass 2: General web search (only if LinkedIn didn't find anyone for this role)
        role_found = any(v["role"] == group["canonical"] for v in found.values())
        if not role_found:
            query = f'"{company}" {group["query_roles"]}'
            results = google_search(query, session, num_results=5)

            for r in results:
                # Try title first
                name = None
                if "linkedin.com" in r.get("url", ""):
                    name = _extract_name_from_linkedin_title(r["title"])

                # Try snippet
                if not name:
                    name = _extract_name_from_snippet(
                        r["title"] + " " + r["snippet"],
                        company,
                        group["keywords"]
                    )

                if name:
                    first, last = parse_name(name)
                    if first and last:
                        key = (first.lower(), last.lower())
                        if key not in found:
                            found[key] = {
                                "first_name": first.title(),
                                "last_name": last.title(),
                                "role": group["canonical"],
                            }
                            print(f"    Found: {first.title()} {last.title()} - {group['canonical']}")

    return list(found.values())
