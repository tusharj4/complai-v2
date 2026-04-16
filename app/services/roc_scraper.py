"""
ROC / MCA Portal Scraper — Complete Implementation (Task 4.1.1)

Scrapes MCA (Ministry of Corporate Affairs) portal for:
- Company master data (CIN, registered address, status)
- Annual filings (MGT-7, AOC-4, etc.)
- Directors (DIN, name, designation, appointment date)
- Charge information
- Financial summary (from annual return filings)
"""

import logging
import re
from datetime import datetime
from typing import Optional
from app.services.scraper import BasePortalScraper

logger = logging.getLogger(__name__)


class ROCScraper(BasePortalScraper):
    """
    Full MCA portal scraper. Handles:
    - Login bypass (public data available without login)
    - Company search by CIN or name
    - Data extraction: master data, filings, directors, charges
    """

    MCA_BASE_URL = "https://www.mca.gov.in"
    COMPANY_SEARCH_URL = f"{MCA_BASE_URL}/mcafoportal/viewCompanyMasterData.do"

    @property
    def version(self) -> str:
        return "2.0.0"

    def scrape(self) -> dict:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        logger.info(f"ROC scrape starting for company: {self.company.name}")

        # Navigate to MCA company search
        self.browser.get(self.COMPANY_SEARCH_URL)

        # Wait for page to be interactive
        WebDriverWait(self.browser, self.timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Search using company name or CIN
        search_input = self._find_search_input()
        if search_input:
            search_input.clear()
            search_input.send_keys(self.company.name)

            submit_btn = self.browser.find_element(By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")
            submit_btn.click()

            WebDriverWait(self.browser, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#resultTable, .company-result, table"))
            )

        # Extract all data sections
        master_data = self._extract_master_data()
        filings = self._extract_filings()
        directors = self._extract_directors()
        charges = self._extract_charges()
        financial_summary = self._derive_financial_summary(filings)

        return {
            "portal": "roc",
            "company_name": self.company.name,
            "master_data": master_data,
            "filings": filings,
            "directors": directors,
            "charges": charges,
            "financial_summary": financial_summary,
            "compliance_status": self._assess_compliance(filings),
            "scraped_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_search_input(self):
        from selenium.webdriver.common.by import By
        selectors = ["#companyID", "#cin", "input[name='companyID']", "input[name='company_name']"]
        for sel in selectors:
            try:
                return self.browser.find_element(By.CSS_SELECTOR, sel)
            except Exception:
                continue
        return None

    def _extract_master_data(self) -> dict:
        """Extract company master data from the result page."""
        from selenium.webdriver.common.by import By
        master = {
            "cin": None,
            "registered_name": None,
            "incorporation_date": None,
            "registered_office": None,
            "company_status": None,
            "company_type": None,
            "roc_code": None,
            "email": None,
        }
        try:
            # Try key-value table format (most MCA pages use this)
            rows = self.browser.find_elements(By.CSS_SELECTOR, ".company-details tr, #masterDataTable tr")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 2:
                    key = cells[0].text.strip().lower().replace(" ", "_").replace(":", "")
                    value = cells[1].text.strip()
                    if "cin" in key:
                        master["cin"] = value
                    elif "registered_name" in key or "company_name" in key:
                        master["registered_name"] = value
                    elif "date_of_incorporation" in key or "incorporated" in key:
                        master["incorporation_date"] = value
                    elif "registered_office" in key or "address" in key:
                        master["registered_office"] = value
                    elif "status" in key:
                        master["company_status"] = value
                    elif "company_type" in key or "class" in key:
                        master["company_type"] = value
                    elif "roc" in key:
                        master["roc_code"] = value
                    elif "email" in key:
                        master["email"] = value
        except Exception as e:
            logger.warning(f"Master data extraction partial: {e}")
        return master

    def _extract_filings(self) -> list:
        """Extract annual filings table (MGT-7, AOC-4, MGT-14, etc.)."""
        from selenium.webdriver.common.by import By
        filings = []
        try:
            rows = self.browser.find_elements(By.CSS_SELECTOR, "#filingTable tr, .filing-table tr")
            for row in rows[1:]:  # Skip header
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 4:
                    filing = {
                        "form_type": cells[0].text.strip(),
                        "filing_date": cells[1].text.strip(),
                        "description": cells[2].text.strip(),
                        "status": cells[3].text.strip(),
                        "srn": cells[4].text.strip() if len(cells) > 4 else None,
                        "is_annual": self._is_annual_filing(cells[0].text.strip()),
                        "period": self._extract_period_from_description(cells[2].text.strip()),
                        "late_fee_paid": "late" in cells[3].text.strip().lower(),
                    }
                    filings.append(filing)
        except Exception as e:
            logger.warning(f"Filing extraction partial: {e}")
        return filings

    def _extract_directors(self) -> list:
        """Extract director information including DIN, designation, appointment date."""
        from selenium.webdriver.common.by import By
        directors = []
        try:
            rows = self.browser.find_elements(By.CSS_SELECTOR, "#directorTable tr, .director-table tr")
            for row in rows[1:]:  # Skip header
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 3:
                    director = {
                        "din": cells[0].text.strip(),
                        "name": cells[1].text.strip(),
                        "designation": cells[2].text.strip(),
                        "appointment_date": cells[3].text.strip() if len(cells) > 3 else None,
                        "cessation_date": cells[4].text.strip() if len(cells) > 4 else None,
                        "is_active": not bool(cells[4].text.strip()) if len(cells) > 4 else True,
                    }
                    directors.append(director)
        except Exception as e:
            logger.warning(f"Director extraction partial: {e}")
        return directors

    def _extract_charges(self) -> list:
        """Extract charge/lien information (secured loans, mortgages)."""
        from selenium.webdriver.common.by import By
        charges = []
        try:
            rows = self.browser.find_elements(By.CSS_SELECTOR, "#chargeTable tr, .charge-table tr")
            for row in rows[1:]:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 4:
                    charges.append({
                        "charge_id": cells[0].text.strip(),
                        "charge_holder": cells[1].text.strip(),
                        "amount": self._parse_amount(cells[2].text.strip()),
                        "creation_date": cells[3].text.strip(),
                        "status": cells[4].text.strip() if len(cells) > 4 else "open",
                    })
        except Exception as e:
            logger.debug(f"Charge extraction (may not be available): {e}")
        return charges

    def _derive_financial_summary(self, filings: list) -> dict:
        """
        Derive financial indicators from filing patterns.
        Real financial data needs AOC-4 document download; this gives signals.
        """
        annual_filings = [f for f in filings if f.get("is_annual")]
        annual_returns = [f for f in filings if "mgt-7" in f.get("form_type", "").lower()]
        balance_sheets = [f for f in filings if "aoc-4" in f.get("form_type", "").lower()]

        return {
            "total_filings": len(filings),
            "annual_returns_filed": len(annual_returns),
            "balance_sheets_filed": len(balance_sheets),
            "late_filings_count": sum(1 for f in filings if f.get("late_fee_paid")),
            "last_annual_return": annual_returns[0]["filing_date"] if annual_returns else None,
            "last_balance_sheet": balance_sheets[0]["filing_date"] if balance_sheets else None,
            "filing_consistency": "good" if len(annual_filings) >= 3 else "insufficient_history",
        }

    def _assess_compliance(self, filings: list) -> str:
        """Simple compliance assessment based on filing patterns."""
        if not filings:
            return "unknown"

        late_count = sum(1 for f in filings if f.get("late_fee_paid"))
        total = len(filings)

        if late_count == 0:
            return "compliant"
        elif late_count / total > 0.3:
            return "at_risk"
        else:
            return "needs_review"

    # ------------------------------------------------------------------
    # Static parsing (used in tests and from HTML snapshots)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_from_html(html: str) -> dict:
        """Parse ROC data from an HTML snapshot (for testing/offline use)."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        filings = []
        filing_table = soup.find(id="filingTable") or soup.find("table", class_="filing-table")
        if filing_table:
            for row in filing_table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) >= 4:
                    filings.append({
                        "form_type": cells[0].get_text(strip=True),
                        "filing_date": cells[1].get_text(strip=True),
                        "description": cells[2].get_text(strip=True),
                        "status": cells[3].get_text(strip=True),
                        "srn": cells[4].get_text(strip=True) if len(cells) > 4 else None,
                        "is_annual": ROCScraper._is_annual_filing_static(cells[0].get_text(strip=True)),
                        "period": None,
                        "late_fee_paid": "late" in cells[3].get_text(strip=True).lower(),
                    })

        directors = []
        dir_table = soup.find(id="directorTable") or soup.find("table", class_="director-table")
        if dir_table:
            for row in dir_table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    directors.append({
                        "din": cells[0].get_text(strip=True),
                        "name": cells[1].get_text(strip=True),
                        "designation": cells[2].get_text(strip=True),
                        "appointment_date": cells[3].get_text(strip=True) if len(cells) > 3 else None,
                        "cessation_date": cells[4].get_text(strip=True) if len(cells) > 4 else None,
                        "is_active": True,
                    })

        return {
            "portal": "roc",
            "filings": filings,
            "directors": directors,
            "charges": [],
            "scraped_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Helper statics
    # ------------------------------------------------------------------

    @staticmethod
    def _is_annual_filing_static(form_type: str) -> bool:
        annual_forms = {"MGT-7", "MGT-7A", "AOC-4", "AOC-4 XBRL", "AOC-4 CFS"}
        return form_type.upper() in annual_forms

    def _is_annual_filing(self, form_type: str) -> bool:
        return self._is_annual_filing_static(form_type)

    def _extract_period_from_description(self, description: str) -> Optional[str]:
        """Try to extract fiscal year period from description text."""
        match = re.search(r"\b(20\d{2}-\d{2,4}|20\d{2}/\d{2,4})\b", description)
        return match.group(1) if match else None

    @staticmethod
    def _parse_amount(text: str) -> Optional[float]:
        cleaned = re.sub(r"[^\d.]", "", text)
        try:
            return float(cleaned)
        except ValueError:
            return None
