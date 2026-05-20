"""Core scraping engine for ScrapePro."""

import hashlib
import logging
import time
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from retrying import retry

from config import ScrapeConfig

logger = logging.getLogger("scrapepro")


class ScrapeResult:
    """Container for scrape results with metadata."""

    def __init__(self, url: str, data: dict[str, Any], raw_html: str = ""):
        self.url = url
        self.data = data
        self.raw_html = raw_html
        self.timestamp = time.time()
        self._hash = hashlib.sha256(raw_html.encode()).hexdigest()[:16]

    @property
    def content_hash(self) -> str:
        return self._hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "timestamp": self.timestamp,
            "content_hash": self.content_hash,
            "data": self.data,
        }


class Scraper:
    """Core scraping engine with rate limiting, retries, and robots.txt."""

    def __init__(self, config: Optional[ScrapeConfig] = None):
        self.config = config or ScrapeConfig()
        self.session = requests.Session()
        self._last_request_time: float = 0
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._results: list[ScrapeResult] = []

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _check_robots(self, url: str) -> bool:
        if not self.config.respect_robots_txt:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            rp = RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                rp.read()
            except Exception:
                return True
            self._robots_cache[base] = rp
        return self._robots_cache[base].can_fetch("*", url)

    @retry(
        stop_max_attempt_number=3,
        wait_exponential_multiplier=1000,
        wait_exponential_max=8000,
    )
    def _fetch(self, url: str) -> requests.Response:
        self._rate_limit()
        headers = self.config.headers.copy()
        headers["User-Agent"] = self.config.get_user_agent()
        proxy = self.config.get_proxy()
        logger.info("Fetching: %s", url)
        resp = self.session.get(
            url,
            headers=headers,
            proxies=proxy,
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        return resp

    def fetch(self, url: str) -> Optional[requests.Response]:
        if not self._check_robots(url):
            logger.warning("Blocked by robots.txt: %s", url)
            return None
        try:
            return self._fetch(url)
        except Exception as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return None

    def scrape(self, url: str) -> Optional[ScrapeResult]:
        resp = self.fetch(url)
        if resp is None:
            return None
        soup = BeautifulSoup(resp.text, "lxml")
        data: dict[str, Any] = {
            "title": self._extract_title(soup),
            "links": self._extract_links(soup, url),
            "images": self._extract_images(soup, url),
            "tables": self._extract_tables(soup),
            "metadata": self._extract_metadata(soup),
            "text": self._extract_text(soup),
        }
        result = ScrapeResult(url, data, resp.text)
        self._results.append(result)
        return result

    def crawl(self, url: str, depth: int = 2) -> list[ScrapeResult]:
        visited: set[str] = set()
        results: list[ScrapeResult] = []
        self._crawl_recursive(url, depth, visited, results)
        return results

    def _crawl_recursive(
        self, url: str, depth: int, visited: set[str], results: list[ScrapeResult]
    ) -> None:
        if depth <= 0 or url in visited:
            return
        visited.add(url)
        result = self.scrape(url)
        if result is None:
            return
        results.append(result)
        for link in result.data.get("links", []):
            href = link.get("href", "")
            if href and href.startswith("http"):
                self._crawl_recursive(href, depth - 1, visited, results)

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        tag = soup.find("title")
        return tag.get_text(strip=True) if tag else ""

    @staticmethod
    def _extract_links(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
        links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"])
            text = a.get_text(strip=True)
            if href and text:
                links.append({"href": href, "text": text})
        return links

    @staticmethod
    def _extract_images(soup: BeautifulSoup, base_url: str) -> list[dict[str, str]]:
        images = []
        for img in soup.find_all("img"):
            src = img.get("src", img.get("data-src", ""))
            if src:
                images.append(
                    {"src": urljoin(base_url, src), "alt": img.get("alt", "")}
                )
        return images

    @staticmethod
    def _extract_tables(soup: BeautifulSoup) -> list[list[list[str]]]:
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [
                    td.get_text(strip=True)
                    for td in tr.find_all(["td", "th"])
                ]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)
        return tables

    @staticmethod
    def _extract_metadata(soup: BeautifulSoup) -> dict[str, str]:
        meta: dict[str, str] = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name", tag.get("property", ""))
            content = tag.get("content", "")
            if name and content:
                meta[name] = content
        return meta

    @staticmethod
    def _extract_text(soup: BeautifulSoup) -> str:
        for tag in soup.find_all(
            ["nav", "footer", "header", "aside", "script", "style"]
        ):
            tag.decompose()
        article = soup.find("article") or soup.find("main") or soup.body
        if article:
            return article.get_text(separator="\n", strip=True)
        return soup.get_text(separator="\n", strip=True)

    @property
    def last_result(self) -> Optional[ScrapeResult]:
        return self._results[-1] if self._results else None

    @staticmethod
    def compare_results(
        result1: ScrapeResult, result2: ScrapeResult
    ) -> dict[str, Any]:
        changes: dict[str, Any] = {
            "url": result1.url,
            "hash_changed": result1.content_hash != result2.content_hash,
            "old_hash": result1.content_hash,
            "new_hash": result2.content_hash,
        }
        if changes["hash_changed"]:
            keys = set(result1.data.keys()) | set(result2.data.keys())
            field_changes = {}
            for key in keys:
                v1 = result1.data.get(key)
                v2 = result2.data.get(key)
                if v1 != v2:
                    field_changes[key] = {"old": v1, "new": v2}
            changes["field_changes"] = field_changes
        return changes
