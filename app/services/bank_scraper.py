import re
import logging
from datetime import datetime
from app.services.scraper import BasePortalScraper

logger = logging.getLogger(__name__)


class BankStatementParser(BasePortalScraper):
    """Parses bank statement PDFs using OCR + pattern matching."""

    def scrape(self) -> dict:
        # Bank statements are uploaded, not scraped from a portal.
        # This uses the extraction pipeline to parse uploaded PDFs.
        raise NotImplementedError("Use parse_statement() for uploaded bank PDFs")

    def parse_statement(self, extracted_text: str) -> dict:
        """Parse extracted text from a bank statement PDF."""
        transactions = self._extract_transactions(extracted_text)
        summary = self._extract_summary(extracted_text)

        return {
            "portal": "bank",
            "transactions": transactions,
            "opening_balance": summary.get("opening_balance"),
            "closing_balance": summary.get("closing_balance"),
            "total_credits": summary.get("total_credits"),
            "total_debits": summary.get("total_debits"),
            "parsed_at": datetime.utcnow().isoformat(),
        }

    def _extract_transactions(self, text: str) -> list:
        """Extract transactions using pattern matching."""
        transactions = []
        # Common bank statement patterns: date, description, debit/credit, balance
        pattern = re.compile(
            r"(\d{2}[/-]\d{2}[/-]\d{4})\s+"  # Date
            r"(.+?)\s+"                         # Description
            r"([\d,]+\.\d{2})?\s*"             # Debit (optional)
            r"([\d,]+\.\d{2})?\s*"             # Credit (optional)
            r"([\d,]+\.\d{2})"                  # Balance
        )

        for match in pattern.finditer(text):
            date_str, desc, debit, credit, balance = match.groups()
            transactions.append({
                "date": date_str,
                "description": desc.strip(),
                "debit": float(debit.replace(",", "")) if debit else 0.0,
                "credit": float(credit.replace(",", "")) if credit else 0.0,
                "balance": float(balance.replace(",", "")),
            })

        return transactions

    def _extract_summary(self, text: str) -> dict:
        """Extract summary fields from statement."""
        summary = {}

        opening = re.search(r"opening\s+balance[:\s]*([\d,]+\.\d{2})", text, re.I)
        if opening:
            summary["opening_balance"] = float(opening.group(1).replace(",", ""))

        closing = re.search(r"closing\s+balance[:\s]*([\d,]+\.\d{2})", text, re.I)
        if closing:
            summary["closing_balance"] = float(closing.group(1).replace(",", ""))

        credits = re.search(r"total\s+credits?[:\s]*([\d,]+\.\d{2})", text, re.I)
        if credits:
            summary["total_credits"] = float(credits.group(1).replace(",", ""))

        debits = re.search(r"total\s+debits?[:\s]*([\d,]+\.\d{2})", text, re.I)
        if debits:
            summary["total_debits"] = float(debits.group(1).replace(",", ""))

        return summary
