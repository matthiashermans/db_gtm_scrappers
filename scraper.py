#!/usr/bin/env python3
"""
Company Executive Scraper & Email Generator

Finds executives in key technical leadership roles at specified companies,
discovers the company's email pattern, and generates their email addresses.

Usage:
    python scraper.py --companies "Datadog, HashiCorp, Cloudflare"
    python scraper.py --file companies.txt
    python scraper.py --companies "Stripe" --output results.csv
"""

import argparse
import csv
import sys

from utils import create_session, company_to_domain
from people_finder import find_people
from email_pattern import discover_email_pattern, generate_email, format_pattern_display


def parse_companies(text):
    """Parse a string of company names (comma, newline, or semicolon separated)."""
    # Split on commas, semicolons, or newlines
    companies = []
    for part in text.replace(';', ',').replace('\n', ',').split(','):
        name = part.strip()
        if name:
            companies.append(name)
    return companies


def run(companies, output_path):
    """Main pipeline: find people, discover email patterns, generate emails."""
    session = create_session()
    all_rows = []

    total = len(companies)
    for idx, company in enumerate(companies, 1):
        print(f"\n[{idx}/{total}] Processing: {company}")
        print("=" * 50)

        # Step 1: Find the company's domain
        domain = company_to_domain(company, session)
        print(f"  Domain: {domain}")

        # Step 2: Find people in target roles
        people = find_people(company, session)
        if not people:
            print(f"  No executives found for {company}")

        # Step 3: Discover email pattern
        pattern = discover_email_pattern(domain, session)
        pattern_display = format_pattern_display(pattern, domain)
        print(f"  Email pattern: {pattern_display}")

        # Step 4: Generate emails and collect rows
        for person in people:
            email = generate_email(
                person["first_name"],
                person["last_name"],
                domain,
                pattern,
            )
            row = {
                "company": company,
                "email_logic": pattern_display,
                "role": person["role"],
                "first_name": person["first_name"],
                "last_name": person["last_name"],
                "email": email,
            }
            all_rows.append(row)
            print(f"  -> {person['first_name']} {person['last_name']} | {person['role']} | {email}")

        print(f"  Found {len(people)} people for {company}")

    # Write CSV output
    if all_rows:
        fieldnames = ["company", "email_logic", "role", "first_name", "last_name", "email"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\nResults written to {output_path} ({len(all_rows)} rows)")
    else:
        print("\nNo results found.")

    return all_rows


def main():
    parser = argparse.ArgumentParser(
        description="Scrape the web for company executives and generate their emails."
    )
    parser.add_argument(
        "-c", "--companies",
        type=str,
        help="Comma-separated list of company names",
    )
    parser.add_argument(
        "-f", "--file",
        type=str,
        help="Path to a text file with one company per line",
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="output.csv",
        help="Output CSV file path (default: output.csv)",
    )

    args = parser.parse_args()

    # Collect companies from arguments
    companies = []

    if args.companies:
        companies.extend(parse_companies(args.companies))

    if args.file:
        try:
            with open(args.file, "r") as f:
                companies.extend(parse_companies(f.read()))
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)

    if not companies:
        # Interactive mode: prompt user to paste companies
        print("No companies provided. Paste company names (comma or newline separated).")
        print("Press Ctrl+D (Linux/Mac) or Ctrl+Z (Windows) when done:\n")
        try:
            text = sys.stdin.read()
            companies = parse_companies(text)
        except EOFError:
            pass

    if not companies:
        print("No companies provided. Use --companies or --file.", file=sys.stderr)
        sys.exit(1)

    print(f"Companies to process: {', '.join(companies)}")
    run(companies, args.output)


if __name__ == "__main__":
    main()
