import logging
from datetime import datetime
from app.services.scraper import BasePortalScraper

logger = logging.getLogger(__name__)


class ROCScraper(BasePortalScraper):
    """Scrapes MCA/ROC portal for annual filings and company data."""

    def scrape(self) -> dict:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        self.browser.get("https://www.mca.gov.in/mcafoportal/viewCompanyMasterData.do")

        WebDriverWait(self.browser, self.timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Search by company CIN or name
        search_input = self.browser.find_element(By.ID, "companyID")
        search_input.send_keys(self.company.name)

        search_btn = self.browser.find_element(By.ID, "submitBtn")
        search_btn.click()

        WebDriverWait(self.browser, self.timeout).until(
            EC.presence_of_element_located((By.ID, "resultTable"))
        )

        filings = self._extract_filings()
        directors = self._extract_directors()

        return {
            "portal": "roc",
            "company_name": self.company.name,
            "filings": filings,
            "directors": directors,
            "scraped_at": datetime.utcnow().isoformat(),
        }

    def _extract_filings(self) -> list:
        from selenium.webdriver.common.by import By
        rows = self.browser.find_elements(By.CSS_SELECTOR, "#filingTable tr")
        filings = []
        for row in rows[1:]:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 4:
                filings.append({
                    "form_type": cells[0].text.strip(),
                    "filing_date": cells[1].text.strip(),
                    "description": cells[2].text.strip(),
                    "status": cells[3].text.strip(),
                })
        return filings

    def _extract_directors(self) -> list:
        from selenium.webdriver.common.by import By
        rows = self.browser.find_elements(By.CSS_SELECTOR, "#directorTable tr")
        directors = []
        for row in rows[1:]:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 3:
                directors.append({
                    "din": cells[0].text.strip(),
                    "name": cells[1].text.strip(),
                    "designation": cells[2].text.strip(),
                })
        return directors
