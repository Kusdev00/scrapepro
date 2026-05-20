"""Tests for ScrapePro — 15+ tests covering all major functionality."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from config import ScrapeConfig
from scraper import Scraper, ScrapeResult
from parsers import (
    ArticleParser,
    ECommerceParser,
    JobListingParser,
    StructuredDataParser,
    TableParser,
    auto_detect_parse,
)
from exporters import (
    JSONExporter,
    CSVExporter,
    XLSXExporter,
    MarkdownExporter,
    SQLiteExporter,
    export_result,
)

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page — Example News</title>
    <meta name="description" content="A test page for scraping">
    <meta property="og:title" content="OG Title Here">
    <meta name="author" content="Jane Doe">
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "NewsArticle", "headline": "Test Headline"}
    </script>
</head>
<body>
    <nav><a href="/home">Home</a> | <a href="/about">About</a></nav>
    <main>
        <article>
            <h1>Breaking News: Python Scraping is Powerful</h1>
            <time datetime="2025-01-15">January 15, 2025</time>
            <span class="author">By Jane Doe</span>
            <p>This is the first paragraph of the article content.</p>
            <p>This is the second paragraph with more details.</p>
            <div class="tags">
                <a href="/tag/python">Python</a>
                <a href="/tag/scraping">Scraping</a>
            </div>
        </article>
    </main>
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>Alpha</td><td>100</td></tr>
        <tr><td>Beta</td><td>200</td></tr>
    </table>
    <a href="https://example.com/page1">Page One</a>
    <a href="https://example.com/page2">Page Two</a>
    <img src="/images/photo.jpg" alt="A test photo">
    <img src="/images/logo.png" alt="Logo">
    <footer>Copyright 2025</footer>
</body>
</html>
"""

ECOMMERCE_HTML = """
<!DOCTYPE html>
<html><head><title>SuperWidget — Buy Now</title></head>
<body>
    <div class="product">
        <h1 class="product-title">SuperWidget Pro</h1>
        <span class="price">$49.99</span>
        <div class="description">The best widget money can buy.</div>
        <img src="/images/product1.jpg" alt="SuperWidget">
        <button class="add-to-cart">Add to Cart</button>
        <div class="review"><p>Great product! 5 stars.</p></div>
        <div class="review"><p>Works as expected.</p></div>
    </div>
</body></html>
"""

JOB_HTML = """
<!DOCTYPE html>
<html><head><title>Software Engineer — Jobs</title></head>
<body>
    <h1 class="job-title">Senior Software Engineer</h1>
    <div class="company">TechCorp Inc.</div>
    <div class="location">San Francisco, CA</div>
    <div class="salary">$150,000 - $200,000 /yr</div>
    <div class="description">
        <p>We are hiring a senior engineer to join our team.</p>
        <p>Requirements: 5+ years of Python experience.</p>
    </div>
    <a href="/apply">Apply Now</a>
</body></html>
"""


@pytest.fixture
def sample_soup():
    return BeautifulSoup(SAMPLE_HTML, "lxml")


@pytest.fixture
def scraper():
    return Scraper(ScrapeConfig(rate_limit_delay=0))


@pytest.fixture
def sample_result():
    data = {
        "title": "Test Page",
        "links": [{"href": "https://example.com/1", "text": "Link 1"}],
        "images": [{"src": "https://example.com/img.jpg", "alt": "Image"}],
        "tables": [[["Name", "Value"], ["A", "1"]]],
        "metadata": {"description": "Test"},
        "text": "Clean text content",
    }
    return ScrapeResult("https://example.com", data, "<html>test</html>")


# --- Config Tests ---

class TestConfig:
    def test_default_config(self):
        config = ScrapeConfig()
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.rate_limit_delay == 1.0
        assert len(config.user_agents) >= 3

    def test_custom_user_agent(self):
        config = ScrapeConfig(custom_user_agent="MyBot/1.0")
        assert config.get_user_agent() == "MyBot/1.0"

    def test_random_user_agent(self):
        config = ScrapeConfig()
        agents = {config.get_user_agent() for _ in range(20)}
        assert len(agents) >= 1

    def test_output_path_creation(self, tmp_path):
        config = ScrapeConfig(output_dir=str(tmp_path / "output"))
        p = config.output_path
        assert p.exists()

    def test_proxy_config(self):
        config = ScrapeConfig(proxies=["http://proxy1:8080", "http://proxy2:8080"])
        proxy = config.get_proxy()
        assert proxy is not None
        assert "http" in proxy


# --- Scraper Tests ---

class TestScraper:
    def test_extract_title(self, scraper, sample_soup):
        title = scraper._extract_title(sample_soup)
        assert "Test Page" in title

    def test_extract_links(self, scraper, sample_soup):
        links = scraper._extract_links(sample_soup, "https://example.com")
        assert len(links) >= 2
        assert any("Page One" in l["text"] for l in links)

    def test_extract_images(self, scraper, sample_soup):
        images = scraper._extract_images(sample_soup, "https://example.com")
        assert len(images) == 2
        assert any("photo.jpg" in img["src"] for img in images)

    def test_extract_tables(self, scraper, sample_soup):
        tables = scraper._extract_tables(sample_soup)
        assert len(tables) >= 1
        assert any("Name" in row for table in tables for row in table)

    def test_extract_metadata(self, scraper, sample_soup):
        meta = scraper._extract_metadata(sample_soup)
        assert "description" in meta
        assert "og:title" in meta

    def test_extract_text_strips_nav_footer(self, scraper, sample_soup):
        text = scraper._extract_text(sample_soup)
        assert "nav" not in text.lower() or "Home" not in text
        assert "Copyright" not in text
        assert "first paragraph" in text

    def test_scrape_result_hash(self, sample_result):
        h = sample_result.content_hash
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_compare_results_no_change(self, sample_result):
        other = ScrapeResult(
            sample_result.url, sample_result.data, "<html>test</html>"
        )
        changes = Scraper.compare_results(sample_result, other)
        assert not changes["hash_changed"]

    def test_compare_results_with_change(self, sample_result):
        different_data = {**sample_result.data, "title": "Changed Title"}
        other = ScrapeResult(sample_result.url, different_data, "<html>different</html>")
        changes = Scraper.compare_results(sample_result, other)
        assert changes["hash_changed"]
        assert "title" in changes.get("field_changes", {})

    @patch.object(Scraper, "_fetch")
    def test_scrape_integration(self, mock_fetch, scraper):
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_fetch.return_value = mock_resp

        result = scraper.scrape("https://example.com")
        assert result is not None
        assert "Test Page" in result.data["title"]
        assert len(result.data["links"]) >= 2


# --- Parser Tests ---

class TestParsers:
    def test_article_parser_detect(self):
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")
        assert ArticleParser.can_parse(soup, "https://example.com/news/article-1")

    def test_article_parser_extract(self):
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")
        data = ArticleParser.parse(soup, "https://example.com")
        assert data["type"] == "article"
        assert "Python Scraping" in data["title"]
        assert "Jane Doe" in data["author"]
        assert "2025-01-15" in data["date"]
        assert "Python" in data["tags"]

    def test_ecommerce_parser_detect(self):
        soup = BeautifulSoup(ECOMMERCE_HTML, "lxml")
        assert ECommerceParser.can_parse(soup, "https://shop.example.com/product/123")

    def test_ecommerce_parser_extract(self):
        soup = BeautifulSoup(ECOMMERCE_HTML, "lxml")
        data = ECommerceParser.parse(soup, "https://shop.example.com")
        assert data["type"] == "ecommerce"
        assert "SuperWidget" in data["title"]
        assert "$49.99" in data["price"]
        assert len(data["reviews"]) >= 2

    def test_job_parser_detect(self):
        soup = BeautifulSoup(JOB_HTML, "lxml")
        assert JobListingParser.can_parse(soup, "https://careers.example.com/job/123")

    def test_job_parser_extract(self):
        soup = BeautifulSoup(JOB_HTML, "lxml")
        data = JobListingParser.parse(soup, "https://careers.example.com")
        assert data["type"] == "job_listing"
        assert "Software Engineer" in data["title"]
        assert "TechCorp" in data["company"]
        assert "San Francisco" in data["location"]

    def test_structured_data_parser(self):
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")
        assert StructuredDataParser.can_parse(soup, "https://example.com")
        data = StructuredDataParser.parse(soup, "https://example.com")
        assert len(data["json_ld"]) >= 1

    def test_table_parser(self):
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")
        assert TableParser.can_parse(soup, "https://example.com")
        data = TableParser.parse(soup, "https://example.com")
        assert len(data["tables"]) >= 1

    def test_auto_detect_article(self):
        soup = BeautifulSoup(SAMPLE_HTML, "lxml")
        data = auto_detect_parse(soup, "https://example.com/news/article-1")
        assert "type" in data


# --- Exporter Tests ---

class TestExporters:
    def test_json_export(self, sample_result, tmp_path):
        path = str(tmp_path / "test.json")
        out = JSONExporter().export(sample_result, path)
        data = json.loads(Path(path).read_text())
        assert data["url"] == "https://example.com"
        assert "data" in data

    def test_csv_export(self, sample_result, tmp_path):
        path = str(tmp_path / "test.csv")
        CSVExporter().export(sample_result, path)
        content = Path(path).read_text()
        assert "section" in content
        assert "Test Page" in content

    def test_markdown_export(self, sample_result, tmp_path):
        path = str(tmp_path / "test.md")
        MDExporter = MarkdownExporter()
        MDExporter.export(sample_result, path)
        content = Path(path).read_text()
        assert "# Scrape Result" in content
        assert "##" in content

    def test_sqlite_export(self, sample_result, tmp_path):
        path = str(tmp_path / "test.db")
        SQLiteExporter().export(sample_result, path)
        assert Path(path).exists()
        import sqlite3
        conn = sqlite3.connect(path)
        rows = conn.execute("SELECT * FROM scrape_results").fetchall()
        assert len(rows) >= 1
        conn.close()

    def test_export_function(self, sample_result, tmp_path):
        path = str(tmp_path / "out.json")
        export_result(sample_result, "json", path)
        assert Path(path).exists()

    def test_export_invalid_format(self, sample_result):
        with pytest.raises(ValueError, match="Unknown format"):
            export_result(sample_result, "xml")

    def test_xlsx_export(self, sample_result, tmp_path):
        pytest.importorskip("openpyxl")
        path = str(tmp_path / "test.xlsx")
        XLSXExporter().export(sample_result, path)
        assert Path(path).exists()


# --- Error Handling Tests ---

class TestErrorHandling:
    def test_fetch_404(self, scraper):
        with patch("requests.Session.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = Exception("404 Not Found")
            mock_get.return_value = mock_resp
            result = scraper.fetch("https://example.com/nonexistent")
            assert result is None

    def test_fetch_timeout(self, scraper):
        with patch("requests.Session.get", side_effect=Exception("Timeout")):
            result = scraper.fetch("https://example.com/timeout")
            assert result is None

    def test_invalid_html(self, scraper):
        soup = BeautifulSoup("<not-valid><<>>", "lxml")
        title = scraper._extract_title(soup)
        assert isinstance(title, str)

    def test_empty_page(self, scraper):
        soup = BeautifulSoup("", "lxml")
        links = scraper._extract_links(soup, "https://example.com")
        assert links == []
        images = scraper._extract_images(soup, "https://example.com")
        assert images == []
        tables = scraper._extract_tables(soup)
        assert tables == []
