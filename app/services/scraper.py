from abc import ABC, abstractmethod
import logging
import time

logger = logging.getLogger(__name__)


class BasePortalScraper(ABC):
    """Base class for all government portal scrapers."""

    def __init__(self, company):
        self.company = company
        self.max_retries = 2
        self.timeout = 30
        self._browser = None

    @property
    def browser(self):
        if self._browser is None:
            from selenium import webdriver
            options = webdriver.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            self._browser = webdriver.Chrome(options=options)
        return self._browser

    @abstractmethod
    def scrape(self) -> dict:
        """Implement portal-specific scraping logic."""
        pass

    def run(self) -> dict:
        """Execute scraper with retries and exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                result = self.scrape()
                logger.info(f"Scraper {self.__class__.__name__} succeeded on attempt {attempt + 1}")
                return {
                    "status": "success",
                    "data": result,
                    "scraper_version": self.version,
                    "attempts": attempt + 1,
                }
            except Exception as e:
                logger.error(f"Scraper {self.__class__.__name__} attempt {attempt + 1} failed: {e}")
                if attempt == self.max_retries - 1:
                    return {
                        "status": "failed",
                        "error": str(e),
                        "attempts": attempt + 1,
                    }
                time.sleep(30 * (2 ** attempt))

    @property
    def version(self) -> str:
        return "1.0.0"

    def cleanup(self):
        if hasattr(self, "_browser") and self._browser is not None:
            try:
                self._browser.quit()
            except Exception:
                pass
            self._browser = None

    def __del__(self):
        if hasattr(self, "_browser"):
            self.cleanup()
