# linkcheck

A fast, multi-threaded broken link checker written in Python. Crawl a website, find dead links, and export a report.

## Features

- Concurrent crawling and checking (configurable thread count)
- Breadth-first crawl with adjustable depth
- Checks `<a>`, `<img>`, `<script>` and `<link>` targets
- Optional external link checking
- HEAD request first, automatic GET fallback for servers that reject HEAD
- Separates **broken** links from **blocked** responses (401/403/429/999)
- Shows which page each broken link was found on
- Exports to JSON or CSV
- Exit code `1` when broken links exist, so it works in CI

## Installation

```bash
git clone https://github.com/khalied75/linkcheck.git
cd linkcheck
pip install -r requirements.txt
```

Requires Python 3.8+.

## Usage

```bash
python linkcheck.py <url> [options]
```

| Option | Description | Default |
|---|---|---|
| `-d, --depth` | Crawl depth | `3` |
| `-w, --workers` | Number of threads | `20` |
| `-t, --timeout` | Request timeout in seconds | `10` |
| `-e, --external` | Also check external links | off |
| `-o, --output` | Save report to `.json` or `.csv` | none |

### Examples

```bash
# Basic scan
python linkcheck.py https://example.com

# Deeper scan, 50 threads, include external links
python linkcheck.py https://example.com -d 5 -w 50 -e

# Save a CSV report
python linkcheck.py https://example.com -o report.csv
```

### Sample output

```
BROKEN                    404  https://example.com/missing.html
                              <- https://example.com/
BROKEN       ConnectionError  https://dead-domain.example/
                              <- https://example.com/links.html

Checked 42 urls: 2 broken, 0 blocked
```

## Use in CI

The script exits with code `1` if any broken link is found:

```yaml
# .github/workflows/linkcheck.yml
name: Link check
on:
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python linkcheck.py https://your-site.com -e -o report.json
```

## Limitations

- Does not execute JavaScript, so links rendered client-side (React, Vue, etc.) are not discovered
- Does not read `robots.txt`
- Some sites block automated requests and will show up as `BLOCKED`

## Responsible use

Only scan sites you own or have permission to crawl. Use a sensible thread count (`-w`) to avoid overloading servers.

## License

MIT. Add a `LICENSE` file to your repo to match.
