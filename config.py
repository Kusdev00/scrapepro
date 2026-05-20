"""Configuration management for ScrapePro."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_USER_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class ScrapeConfig:
    """Central configuration for all scraping operations."""

    # Network
    timeout: int = 30
    max_retries: int = 3
    retry_backoff: float = 2.0
    rate_limit_delay: float = 1.0
    max_concurrent: int = 5

    # Headers
    user_agents: list[str] = field(default_factory=lambda: DEFAULT_USER_AGENTS[:])
    headers: dict[str, str] = field(default_factory=lambda: DEFAULT_HEADERS.copy())
    custom_user_agent: Optional[str] = None

    # Proxies
    proxies: list[str] = field(default_factory=list)
    rotate_proxies: bool = False

    # Crawling
    max_depth: int = 2
    respect_robots_txt: bool = True
    allowed_domains: list[str] = field(default_factory=list)

    # Output
    output_dir: str = "scrape_output"
    default_format: str = "json"
    verbose: bool = False

    # JS rendering
    render_js: bool = False
    js_wait: int = 3

    @property
    def output_path(self) -> Path:
        p = Path(self.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def get_user_agent(self) -> str:
        if self.custom_user_agent:
            return self.custom_user_agent
        import random
        return random.choice(self.user_agents)

    def get_proxy(self) -> Optional[dict[str, str]]:
        if not self.proxies:
            return None
        import random
        proxy = random.choice(self.proxies)
        return {"http": proxy, "https": proxy}
