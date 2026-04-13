import logging
from datetime import datetime
from app.services.scraper import BasePortalScraper

logger = logging.getLogger(__name__)


class GSTScraper(BasePortalScraper):
    """
    Scrapes GST portal for return filing data.
    Requires: company.filing_deadlines for context.
    """

    def scrape(self) -> dict:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        # Navigate to GST portal
        self.browser.get("https://services.gst.gov.in")

        # Wait for page load
        WebDriverWait(self.browser, self.timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Login flow
        username_input = self.browser.find_element(By.ID, "userid")
        password_input = self.browser.find_element(By.ID, "password")

        # Credentials should come from secure vault - not hardcoded
        credentials = self._get_credentials()
        username_input.send_keys(credentials["username"])
        password_input.send_keys(credentials["password"])

        login_btn = self.browser.find_element(By.ID, "submitButton")
        login_btn.click()

        # Wait for dashboard
        WebDriverWait(self.browser, self.timeout).until(
            EC.presence_of_element_located((By.ID, "returns_table"))
        )

        # Extract returns table
        returns_html = self.browser.find_element(By.ID, "returns_table").get_attribute("outerHTML")
        returns_data = self._parse_returns(returns_html)

        return {
            "portal": "gst",
            "gst_id": self.company.gst_id,
            "returns": returns_data,
            "scraped_at": datetime.utcnow().isoformat(),
        }

    def _get_credentials(self) -> dict:
        """Retrieve credentials from secure storage."""
        # TODO: Integrate with vault/secrets manager
        return {"username": "placeholder", "password": "placeholder"}

    def _parse_returns(self, html: str) -> list:
        """Parse returns table HTML into structured data."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr")[1:]  # Skip header

        returns = []
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 3:
                returns.append({
                    "filing_period": cells[0].text.strip(),
                    "status": cells[1].text.strip(),
                    "due_date": cells[2].text.strip(),
                    "filed_date": cells[3].text.strip() if len(cells) > 3 else None,
                })

        return returns

    @staticmethod
    def parse_returns_from_html(html: str) -> list:
        """Public static method for testing parse logic without browser."""
        scraper = GSTScraper.__new__(GSTScraper)
        return scraper._parse_returns(html)
