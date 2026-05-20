# ScrapePro Lite — Professional Web Scraping Toolkit

```
  ╔═╗┌─┐┬─┐┌─┐┌─┐┌─┐╔═╗┬─┐┌─┐
  ╚═╗│  ├┬┘├─┤├─┘├─╚╗╠═╝├┬┘│ │
  ╚═╝└─┘┴└─┴ ┴┴  └─╚╝╩  ┴└─└─┘
  Professional Web Scraping Toolkit
```

A fast, lightweight CLI tool for web scraping and data extraction.
Built with Python — no browser required.

## What It Does

ScrapePro Lite scrapes **static HTML pages** — blogs, news sites, e-commerce
product pages, job boards, directories, and any server-rendered website.

**Best for:**
- News sites & blogs
- E-commerce product pages
- Job listing sites
- Business directories
- Wikipedia & documentation sites
- Any server-rendered HTML

**Not for:** JavaScript-heavy sites like YouTube, Twitter/X, Instagram, or
modern SPAs. For those, check out [ScrapePro Full](https://kusdev.gumroad.com/l/scrapepro).

## Features

- Smart scraping — auto-detects page structure and extracts all useful data
- CSS selector and XPath extraction
- Table extraction from any HTML tables
- Article text extraction (strips nav, ads, footers)
- Metadata extraction (meta tags, OpenGraph, JSON-LD)
- Site crawling with configurable depth
- Change detection for monitoring
- Export to JSON, CSV, XLSX, Markdown, and SQLite
- Rate limiting and polite crawling (respects robots.txt)
- Retry logic with exponential backoff
- Beautiful terminal output with progress bars
- Auto-detection of page types (e-commerce, articles, job listings)

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Smart Scrape (Auto-Detect)

```bash
python main.py scrape https://example.com
```

### CSS Selector Extraction

```bash
python main.py scrape https://news.ycombinator.com --css ".titleline > a"
python main.py scrape https://example.com --css "h2.article-title"
```

### XPath Extraction

```bash
python main.py scrape https://example.com --xpath "//h1/text()"
python main.py scrape https://example.com --xpath "//div[@class='price']/text()"
```

### Extract Specific Data

```bash
python main.py scrape https://en.wikipedia.org/wiki/Python_(programming_language) --tables
python main.py scrape https://example.com --links
python main.py scrape https://example.com --images
python main.py scrape https://example.com --metadata
python main.py scrape https://example.com/blog/post-1 --text
```

### Crawl a Site

```bash
python main.py crawl https://example.com --depth 3
```

### Export Results

```bash
python main.py scrape https://example.com
python main.py export json
python main.py export csv
python main.py export xlsx
python main.py export md
python main.py export sqlite
```

### Monitor for Changes

```bash
python main.py schedule https://example.com --interval 60
```

### Compare Scrape Results

```bash
python main.py compare snapshot_1.json snapshot_2.json
```

### Demo Mode

```bash
python main.py --demo
```

## Project Structure

```
lite/
├── main.py           # CLI entry point
├── scraper.py        # Core scraping engine
├── parsers.py        # Specialized page-type parsers
├── exporters.py      # Export to JSON/CSV/XLSX/MD/SQLite
├── config.py         # Configuration management
├── test_scraper.py   # 35 tests
├── requirements.txt  # Dependencies
└── README.md         # This file
```

## Running Tests

```bash
pip install pytest
pytest test_scraper.py -v
```

## Dependencies

- `requests` — HTTP client
- `beautifulsoup4` + `lxml` — HTML parsing
- `rich` — Beautiful terminal output
- `click` — CLI framework
- `openpyxl` — Excel export
- `fake-useragent` — User agent rotation
- `retrying` — Retry logic

## Upgrading to Pro

Need JavaScript rendering for YouTube, Twitter, or modern SPAs?
[ScrapePro Full](https://kusdev.gumroad.com/l/scrapepro) adds Playwright-powered headless browser rendering
while keeping all the same features.

## License

MIT
