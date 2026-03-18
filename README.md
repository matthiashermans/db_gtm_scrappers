# Company Executive Scraper

Scrapes the web to find executives in key technical leadership roles at specified companies, discovers email naming patterns, and generates email addresses.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Single or multiple companies
python scraper.py --companies "Datadog, HashiCorp, Cloudflare"

# From a file (one company per line)
python scraper.py --file companies.txt

# Custom output path
python scraper.py --companies "Stripe" --output results.csv

# Interactive mode
python scraper.py
```

## Target Roles

- Director / Head of Platform
- Director / Head of SRE
- Head / Director of Infrastructure
- VP Engineering
- CTO
- CIO

## Output

CSV with columns: company, email_logic, role, first_name, last_name, email

