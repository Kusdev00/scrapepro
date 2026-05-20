"""Specialized parsers for common web page types."""

import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup


class BaseParser:
    """Base class for all specialized parsers."""

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str) -> bool:
        return False

    @classmethod
    def parse(cls, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        return {}


class ECommerceParser(BaseParser):
    """Parser for e-commerce product pages."""

    INDICATORS = ["product", "price", "add-to-cart", "buy", "cart", "shop"]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str) -> bool:
        url_lower = url.lower()
        text_lower = soup.get_text().lower()
        score = sum(1 for ind in cls.INDICATORS if ind in url_lower)
        score += sum(1 for ind in cls.INDICATORS if ind in text_lower[:2000])
        return score >= 3

    @classmethod
    def parse(cls, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": "ecommerce",
            "title": cls._get_title(soup),
            "price": cls._get_price(soup),
            "description": cls._get_description(soup),
            "images": cls._get_images(soup, url),
            "reviews": cls._get_reviews(soup),
        }
        return data

    @staticmethod
    def _get_title(soup: BeautifulSoup) -> str:
        for sel in ["h1", "[class*='product-title']", "[class*='product-name']", "[itemprop='name']"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _get_price(soup: BeautifulSoup) -> str:
        price_pattern = re.compile(r"[\$€£¥]\s*[\d,]+\.?\d*")
        for sel in ["[class*='price']", "[itemprop='price']", ".price", "#price"]:
            tag = soup.select_one(sel)
            if tag:
                text = tag.get_text(strip=True)
                match = price_pattern.search(text)
                if match:
                    return match.group()
        text = soup.get_text()
        match = price_pattern.search(text)
        return match.group() if match else ""

    @staticmethod
    def _get_description(soup: BeautifulSoup) -> str:
        for sel in ["[class*='description']", "[itemprop='description']", "#description"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _get_images(soup: BeautifulSoup, base_url: str) -> list[str]:
        from urllib.parse import urljoin
        images = []
        for img in soup.find_all("img"):
            src = img.get("src", img.get("data-src", ""))
            if src and "product" in src.lower():
                images.append(urljoin(base_url, src))
        return images

    @staticmethod
    def _get_reviews(soup: BeautifulSoup) -> list[dict[str, str]]:
        reviews = []
        for sel in ["[class*='review']", "[class*='comment']"]:
            for item in soup.select(sel)[:5]:
                text = item.get_text(strip=True)
                if text:
                    reviews.append({"text": text[:200]})
        return reviews


class ArticleParser(BaseParser):
    """Parser for news/article pages."""

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str) -> bool:
        if soup.find("article"):
            return True
        if any(x in url for x in ["/news/", "/article/", "/blog/", "/post/"]):
            return True
        return bool(soup.find("time") and soup.find("h1"))

    @classmethod
    def parse(cls, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        return {
            "type": "article",
            "title": cls._get_title(soup),
            "author": cls._get_author(soup),
            "date": cls._get_date(soup),
            "content": cls._get_content(soup),
            "tags": cls._get_tags(soup),
        }

    @staticmethod
    def _get_title(soup: BeautifulSoup) -> str:
        for sel in ["h1", "[class*='headline']", "[itemprop='headline']"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _get_author(soup: BeautifulSoup) -> str:
        for sel in ["[class*='author']", "[rel='author']", "[itemprop='author']"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _get_date(soup: BeautifulSoup) -> str:
        time_tag = soup.find("time")
        if time_tag:
            return time_tag.get("datetime", time_tag.get_text(strip=True))
        for sel in ["[class*='date']", "[class*='published']", "[itemprop='datePublished']"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _get_content(soup: BeautifulSoup) -> str:
        article = soup.find("article") or soup.find("main") or soup.body
        if article:
            for tag in article.find_all(["nav", "footer", "aside", "script", "style"]):
                tag.decompose()
            return article.get_text(separator="\n", strip=True)
        return ""

    @staticmethod
    def _get_tags(soup: BeautifulSoup) -> list[str]:
        tags = []
        for a in soup.find_all("a", href=True):
            if any(x in a["href"].lower() for x in ["/tag/", "/category/", "/topic/"]):
                text = a.get_text(strip=True)
                if text:
                    tags.append(text)
        return list(set(tags))


class JobListingParser(BaseParser):
    """Parser for job listing pages."""

    KEYWORDS = ["job", "career", "hiring", "position", "salary", "apply"]

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str) -> bool:
        combined = (url + soup.get_text()[:2000]).lower()
        return sum(1 for kw in cls.KEYWORDS if kw in combined) >= 3

    @classmethod
    def parse(cls, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        return {
            "type": "job_listing",
            "title": cls._get_title(soup),
            "company": cls._get_company(soup),
            "location": cls._get_location(soup),
            "salary": cls._get_salary(soup),
            "description": cls._get_description(soup),
        }

    @staticmethod
    def _get_title(soup: BeautifulSoup) -> str:
        for sel in ["h1", "[class*='job-title']", "[class*='position']"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _get_company(soup: BeautifulSoup) -> str:
        for sel in ["[class*='company']", "[class*='employer']", "[itemprop='hiringOrganization']"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _get_location(soup: BeautifulSoup) -> str:
        for sel in ["[class*='location']", "[itemprop='jobLocation']"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(strip=True)
        return ""

    @staticmethod
    def _get_salary(soup: BeautifulSoup) -> str:
        pattern = re.compile(r"[\$€£]\s*[\d,]+\s*[-–to]*\s*[\$€£]?\s*[\d,]+\s*(?:/yr|/year|/month|/hr|annually)?", re.I)
        text = soup.get_text()
        match = pattern.search(text)
        return match.group() if match else ""

    @staticmethod
    def _get_description(soup: BeautifulSoup) -> str:
        for sel in ["[class*='description']", "[class*='details']", "article", "main"]:
            tag = soup.select_one(sel)
            if tag:
                return tag.get_text(separator="\n", strip=True)[:2000]
        return ""


class StructuredDataParser(BaseParser):
    """Extract JSON-LD and microdata structured data."""

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str) -> bool:
        return bool(soup.find("script", type="application/ld+json"))

    @classmethod
    def parse(cls, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        data: dict[str, Any] = {"type": "structured_data", "json_ld": []}
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                parsed = json.loads(script.string)
                data["json_ld"].append(parsed)
            except (json.JSONDecodeError, TypeError):
                continue
        return data


class TableParser(BaseParser):
    """Extract all HTML tables as structured data."""

    @classmethod
    def can_parse(cls, soup: BeautifulSoup, url: str) -> bool:
        return bool(soup.find("table"))

    @classmethod
    def parse(cls, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        tables = []
        for table in soup.find_all("table"):
            headers = []
            rows = []
            for i, tr in enumerate(table.find_all("tr")):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    if i == 0 and all(
                        td.name == "th" for td in tr.find_all(["td", "th"])
                    ):
                        headers = cells
                    else:
                        rows.append(cells)
            tables.append({"headers": headers, "rows": rows})
        return {"type": "tables", "tables": tables}


PARSERS = [
    ECommerceParser,
    ArticleParser,
    JobListingParser,
    StructuredDataParser,
    TableParser,
]


def auto_detect_parse(soup: BeautifulSoup, url: str) -> dict[str, Any]:
    """Run all parsers that can handle the page and merge results."""
    results: dict[str, Any] = {}
    for parser_cls in PARSERS:
        if parser_cls.can_parse(soup, url):
            parsed = parser_cls.parse(soup, url)
            results.update(parsed)
    return results
