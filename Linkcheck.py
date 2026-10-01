#!/usr/bin/env python3
"""linkcheck.py - crawl a site and report broken links.

Install:  pip install requests beautifulsoup4
Usage:    python linkcheck.py https://example.com -d 3 -w 20 --external -o report.json
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:")
BLOCKED = {401, 403, 429, 999}  # site blocked the bot; not necessarily broken
TAGS = (("a", "href"), ("img", "src"), ("script", "src"), ("link", "href"))


def make_session(workers):
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; linkcheck/1.0)"
    adapter = HTTPAdapter(pool_connections=workers, pool_maxsize=workers, max_retries=1)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s


def extract_links(base, html):
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for tag, attr in TAGS:
        for el in soup.find_all(tag, attrs={attr: True}):
            raw = el[attr].strip()
            if not raw or raw.startswith("#") or raw.lower().startswith(SKIP_SCHEMES):
                continue
            url = urldefrag(urljoin(base, raw))[0]
            if urlparse(url).scheme in ("http", "https"):
                found.add(url)
    return found


def probe(session, url, timeout, crawl):
    """Return (url, status_code | None, error | None, discovered_links)."""
    links = set()
    try:
        if crawl:
            r = session.get(url, timeout=timeout)
            if r.status_code < 400 and "html" in r.headers.get("Content-Type", ""):
                links = extract_links(r.url, r.text)
        else:
            r = session.head(url, timeout=timeout, allow_redirects=True)
            if r.status_code >= 400:  # some servers reject HEAD; retry with GET
                r = session.get(url, timeout=timeout, stream=True)
                r.close()
        return url, r.status_code, None, links
    except requests.RequestException as e:
        return url, None, type(e).__name__, links


def crawl_site(start, depth, workers, timeout, check_external):
    host = urlparse(start).netloc.lower()
    internal = lambda u: urlparse(u).netloc.lower() == host

    session = make_session(workers)
    results = {}                      # url -> (status, error)
    sources = defaultdict(set)        # url -> pages that link to it
    seen = {start}
    frontier = [start]
    level = 0

    while frontier and level <= depth:
        nxt = []
        print(f"[level {level}] checking {len(frontier)} url(s)", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [
                ex.submit(probe, session, u, timeout, internal(u) and level < depth)
                for u in frontier
            ]
            for f in as_completed(futs):
                url, code, err, links = f.result()
                results[url] = (code, err)
                for link in links:
                    if not internal(link) and not check_external:
                        continue
                    sources[link].add(url)
                    if link not in seen:
                        seen.add(link)
                        nxt.append(link)
        frontier, level = nxt, level + 1

    return results, sources


def classify(code, err):
    if code is None:
        return "broken"
    if code in BLOCKED:
        return "blocked"
    return "broken" if code >= 400 else "ok"


def main():
    p = argparse.ArgumentParser(description="Crawl a site and report broken links.")
    p.add_argument("url")
    p.add_argument("-d", "--depth", type=int, default=3, help="crawl depth (default 3)")
    p.add_argument("-w", "--workers", type=int, default=20, help="threads (default 20)")
    p.add_argument("-t", "--timeout", type=float, default=10, help="seconds (default 10)")
    p.add_argument("-e", "--external", action="store_true", help="also check external links")
    p.add_argument("-o", "--output", help="write report to .json or .csv")
    args = p.parse_args()

    if not urlparse(args.url).scheme:
        args.url = "https://" + args.url

    results, sources = crawl_site(
        args.url, args.depth, args.workers, args.timeout, args.external
    )

    rows = []
    for url, (code, err) in sorted(results.items()):
        state = classify(code, err)
        if state != "ok":
            rows.append({
                "state": state,
                "status": code if code is not None else err,
                "url": url,
                "found_on": sorted(sources.get(url, [])),
            })

    broken = [r for r in rows if r["state"] == "broken"]
    for r in rows:
        print(f"{r['state'].upper():8} {str(r['status']):>20}  {r['url']}")
        for page in r["found_on"][:3]:
            print(f"{'':30}<- {page}")

    print(f"\nChecked {len(results)} urls: {len(broken)} broken, "
          f"{len(rows) - len(broken)} blocked", file=sys.stderr)

    if args.output:
        if args.output.endswith(".csv"):
            with open(args.output, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["state", "status", "url", "found_on"])
                for r in rows:
                    w.writerow([r["state"], r["status"], r["url"], " | ".join(r["found_on"])])
        else:
            with open(args.output, "w") as fh:
                json.dump(rows, fh, indent=2)

    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
