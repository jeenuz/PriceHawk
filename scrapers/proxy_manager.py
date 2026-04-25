import random
import os
from loguru import logger


class ProxyManager:
    """
    Manages a list of free proxies with rotation and health tracking.
    Removes proxies that fail too many times.
    """

    def __init__(self, proxy_file: str = "scrapers/proxies.txt"):
        self.proxies = self._load_proxies(proxy_file)
        self.failed_counts = {}     # track failures per proxy
        self.max_failures = 3       # remove proxy after 3 failures
        logger.info(f"Loaded {len(self.proxies)} proxies")

    def _load_proxies(self, filepath: str) -> list[str]:
        """Load proxies from file — skip comments and empty lines."""
        if not os.path.exists(filepath):
            logger.warning(f"Proxy file not found: {filepath}")
            return []

        proxies = []
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith("#"):
                    # Ensure http:// prefix
                    if not line.startswith("http"):
                        line = f"http://{line}"
                    proxies.append(line)

        return proxies

    def get_random_proxy(self) -> str | None:
        """Get a random working proxy."""
        if not self.proxies:
            logger.warning("No proxies available!")
            return None

        proxy = random.choice(self.proxies)
        logger.debug(f"Using proxy: {proxy}")
        return proxy

    def mark_failed(self, proxy: str):
        """Mark a proxy as failed — remove after max_failures."""
        if not proxy:
            return

        self.failed_counts[proxy] = self.failed_counts.get(proxy, 0) + 1

        if self.failed_counts[proxy] >= self.max_failures:
            if proxy in self.proxies:
                self.proxies.remove(proxy)
                logger.warning(
                    f"Removed proxy after {self.max_failures} "
                    f"failures: {proxy}"
                )
                logger.info(f"Remaining proxies: {len(self.proxies)}")

    def mark_success(self, proxy: str):
        """Reset failure count on success."""
        if proxy in self.failed_counts:
            self.failed_counts[proxy] = 0

    def get_playwright_proxy(self) -> dict | None:
        """
        Get proxy in Playwright format.
        Returns None if no proxies available.
        """
        proxy = self.get_random_proxy()
        if not proxy:
            return None

        return {
            "server": proxy,
        }

    @property
    def count(self) -> int:
        return len(self.proxies)