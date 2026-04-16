"""
Bank Statement Parser — Complete Multi-Bank Implementation (Task 4.1.2)

Supports statement formats from:
- ICICI Bank
- HDFC Bank
- Axis Bank
- SBI (State Bank of India)
- Kotak Mahindra Bank
- Generic fallback (any tabular bank statement)

Usage:
    parser = BankStatementParser(company)  # company can be None for standalone use
    result = parser.parse_statement(extracted_text, bank_hint="icici")
"""

import re
import logging
from datetime import datetime
from typing import Optional
from app.services.scraper import BasePortalScraper

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bank-specific regex patterns
# ---------------------------------------------------------------------------

BANK_PATTERNS = {
    "icici": {
        # ICICI format: DD/MM/YYYY  Description  Withdrawal  Deposit  Balance
        "transaction": re.compile(
            r"(\d{2}/\d{2}/\d{4})\s+"          # Date
            r"(.+?)\s{2,}"                        # Description (>=2 spaces as separator)
            r"([\d,]+\.\d{2})?\s*"              # Withdrawal (debit)
            r"([\d,]+\.\d{2})?\s*"              # Deposit (credit)
            r"([\d,]+\.\d{2}(?:\s*Cr)?)"        # Balance
        ),
        "opening": re.compile(r"opening\s+balance[:\s]+([\d,]+\.\d{2})", re.I),
        "closing": re.compile(r"closing\s+balance[:\s]+([\d,]+\.\d{2})", re.I),
        "date_format": "%d/%m/%Y",
    },
    "hdfc": {
        # HDFC format: DD/MM/YY  Narration  Chq/Ref  Value Date  Withdrawal  Deposit  Closing Balance
        "transaction": re.compile(
            r"(\d{2}/\d{2}/\d{2,4})\s+"         # Date
            r"(.+?)\s+"                            # Narration
            r"[\w\d]*/?\s*"                        # Chq/Ref (optional)
            r"\d{2}/\d{2}/\d{2,4}\s+"             # Value date
            r"([\d,]+\.\d{2})?\s*"               # Withdrawal
            r"([\d,]+\.\d{2})?\s*"               # Deposit
            r"([\d,]+\.\d{2})"                    # Closing balance
        ),
        "opening": re.compile(r"opening\s+balance[:\s]+([\d,]+\.\d{2})", re.I),
        "closing": re.compile(r"closing\s+balance[:\s]+([\d,]+\.\d{2})", re.I),
        "date_format": "%d/%m/%y",
    },
    "axis": {
        # Axis format: Tran Date  Chq No  Particulars  Debit  Credit  Balance
        "transaction": re.compile(
            r"(\d{2}-\d{2}-\d{4})\s+"            # Date (DD-MM-YYYY)
            r"(\d{6,})?\s*"                        # Cheque number (optional)
            r"(.+?)\s{2,}"                         # Particulars
            r"([\d,]+\.\d{2})?\s*"               # Debit
            r"([\d,]+\.\d{2})?\s*"               # Credit
            r"([\d,]+\.\d{2})"                    # Balance
        ),
        "opening": re.compile(r"opening\s+balance[:\s]+([\d,]+\.\d{2})", re.I),
        "closing": re.compile(r"closing\s+balance[:\s]+([\d,]+\.\d{2})", re.I),
        "date_format": "%d-%m-%Y",
    },
    "sbi": {
        # SBI format: Txn Date  Value Date  Description  Ref No./Cheque No.  Debit  Credit  Balance
        "transaction": re.compile(
            r"(\d{2}\s+\w{3}\s+\d{4})\s+"        # Date (DD Mon YYYY)
            r"(\d{2}\s+\w{3}\s+\d{4})\s+"        # Value date
            r"(.+?)\s{2,}"                         # Description
            r"[\w\d]*/?\s*"                        # Ref/Cheque no.
            r"([\d,]+\.\d{2})?\s*"               # Debit
            r"([\d,]+\.\d{2})?\s*"               # Credit
            r"([\d,]+\.\d{2})"                    # Balance
        ),
        "opening": re.compile(r"(?:opening|ob)\s*[:\s]+([\d,]+\.\d{2})", re.I),
        "closing": re.compile(r"(?:closing|cb)\s*[:\s]+([\d,]+\.\d{2})", re.I),
        "date_format": "%d %b %Y",
    },
    "kotak": {
        "transaction": re.compile(
            r"(\d{2}-\d{2}-\d{4})\s+"
            r"(.+?)\s{2,}"
            r"([\d,]+\.\d{2})?\s*"
            r"([\d,]+\.\d{2})?\s*"
            r"([\d,]+\.\d{2})"
        ),
        "opening": re.compile(r"opening\s+balance[:\s]+([\d,]+\.\d{2})", re.I),
        "closing": re.compile(r"closing\s+balance[:\s]+([\d,]+\.\d{2})", re.I),
        "date_format": "%d-%m-%Y",
    },
}

# Generic fallback — matches most common tabular formats
GENERIC_PATTERN = re.compile(
    r"(\d{2}[/\-]\d{2}[/\-]\d{2,4})\s+"
    r"(.+?)\s{2,}"
    r"([\d,]+\.\d{2})?\s*"
    r"([\d,]+\.\d{2})?\s*"
    r"([\d,]+\.\d{2})"
)


class BankStatementParser(BasePortalScraper):
    """
    Parses bank statement PDFs/text using format-aware pattern matching.
    Auto-detects bank format when bank_hint is not provided.
    """

    def scrape(self) -> dict:
        # Bank statements are uploaded (not live-scraped from portal).
        # The actual parsing happens via parse_statement().
        raise NotImplementedError(
            "Bank statements use parse_statement(extracted_text). "
            "Use the document intake pipeline to upload PDFs."
        )

    def parse_statement(self, extracted_text: str, bank_hint: Optional[str] = None) -> dict:
        """
        Parse extracted text from a bank statement PDF.

        Args:
            extracted_text: Raw text from OCR or PDF extraction.
            bank_hint: Optional bank name ('icici', 'hdfc', 'axis', 'sbi', 'kotak').
                       If None, auto-detection is attempted.

        Returns:
            Parsed statement dict with transactions and summary.
        """
        bank = bank_hint.lower() if bank_hint else self._detect_bank(extracted_text)
        logger.info(f"Parsing bank statement as: {bank}")

        transactions = self._extract_transactions(extracted_text, bank)
        summary = self._extract_summary(extracted_text, bank)
        reconciliation = self._reconciliation_check(transactions, summary)

        return {
            "portal": "bank",
            "bank_detected": bank,
            "transactions": transactions,
            "transaction_count": len(transactions),
            "opening_balance": summary.get("opening_balance"),
            "closing_balance": summary.get("closing_balance"),
            "total_credits": summary.get("total_credits") or self._sum_credits(transactions),
            "total_debits": summary.get("total_debits") or self._sum_debits(transactions),
            "reconciliation": reconciliation,
            "parsed_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    def _detect_bank(self, text: str) -> str:
        """Detect bank from characteristic strings in statement header."""
        text_upper = text[:2000].upper()  # Check header section only

        signatures = {
            "icici": ["ICICI BANK", "ICICIBANK", "ICICI BANK LTD"],
            "hdfc": ["HDFC BANK", "HDFCBANK", "HDFC BANK LTD"],
            "axis": ["AXIS BANK", "AXISBANK", "AXIS BANK LTD"],
            "sbi": ["STATE BANK OF INDIA", "SBI", "SBI BANK"],
            "kotak": ["KOTAK MAHINDRA", "KOTAK BANK", "KOTAK"],
        }

        for bank, markers in signatures.items():
            if any(m in text_upper for m in markers):
                logger.debug(f"Detected bank: {bank}")
                return bank

        return "generic"

    # ------------------------------------------------------------------
    # Transaction extraction
    # ------------------------------------------------------------------

    def _extract_transactions(self, text: str, bank: str) -> list:
        """Extract transactions using bank-specific or generic patterns."""
        pattern_info = BANK_PATTERNS.get(bank)
        pattern = pattern_info["transaction"] if pattern_info else GENERIC_PATTERN

        transactions = []
        seen_hashes = set()

        for match in pattern.finditer(text):
            groups = match.groups()

            if bank == "axis":
                date_str, chq, desc, debit, credit, balance = groups
            elif bank == "sbi":
                date_str, _val_date, desc, debit, credit, balance = groups
            else:
                date_str, desc, debit, credit, balance = groups[:5]

            debit_val = self._parse_amount(debit)
            credit_val = self._parse_amount(credit)
            balance_val = self._parse_amount(balance)

            if balance_val is None:
                continue  # Skip rows without balance (likely headers)

            desc_clean = (desc or "").strip()

            # Dedup by date+description+amount
            txn_key = f"{date_str}|{desc_clean}|{debit_val}|{credit_val}"
            if txn_key in seen_hashes:
                continue
            seen_hashes.add(txn_key)

            transactions.append({
                "date": date_str.strip(),
                "description": desc_clean,
                "debit": debit_val or 0.0,
                "credit": credit_val or 0.0,
                "balance": balance_val,
                "transaction_type": "debit" if (debit_val or 0) > 0 else "credit",
            })

        # Sort by date if parseable
        transactions = self._sort_transactions(transactions, bank)
        return transactions

    # ------------------------------------------------------------------
    # Summary extraction
    # ------------------------------------------------------------------

    def _extract_summary(self, text: str, bank: str) -> dict:
        """Extract summary fields using bank-specific patterns."""
        summary = {}
        pattern_info = BANK_PATTERNS.get(bank, {})

        opening_pat = pattern_info.get("opening") or re.compile(
            r"opening\s+balance[:\s]*([\d,]+\.\d{2})", re.I
        )
        closing_pat = pattern_info.get("closing") or re.compile(
            r"closing\s+balance[:\s]*([\d,]+\.\d{2})", re.I
        )

        m = opening_pat.search(text)
        if m:
            summary["opening_balance"] = self._parse_amount(m.group(1))

        m = closing_pat.search(text)
        if m:
            summary["closing_balance"] = self._parse_amount(m.group(1))

        # Total credits / debits — some banks print these explicitly
        credits_pat = re.compile(r"total\s+credits?[:\s]*([\d,]+\.\d{2})", re.I)
        debits_pat = re.compile(r"total\s+debits?[:\s]*([\d,]+\.\d{2})", re.I)

        m = credits_pat.search(text)
        if m:
            summary["total_credits"] = self._parse_amount(m.group(1))

        m = debits_pat.search(text)
        if m:
            summary["total_debits"] = self._parse_amount(m.group(1))

        return summary

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def _reconciliation_check(self, transactions: list, summary: dict) -> dict:
        """
        Verify: opening_balance + total_credits - total_debits ≈ closing_balance
        """
        opening = summary.get("opening_balance")
        closing = summary.get("closing_balance")
        total_credits = summary.get("total_credits") or self._sum_credits(transactions)
        total_debits = summary.get("total_debits") or self._sum_debits(transactions)

        if opening is None or closing is None:
            return {"status": "insufficient_data", "variance": None}

        expected_closing = opening + total_credits - total_debits
        variance = abs(expected_closing - closing)
        tolerance = 1.0  # ₹1 tolerance for rounding

        return {
            "status": "balanced" if variance <= tolerance else "variance_detected",
            "opening_balance": opening,
            "total_credits": total_credits,
            "total_debits": total_debits,
            "expected_closing": round(expected_closing, 2),
            "actual_closing": closing,
            "variance": round(variance, 2),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_amount(text: Optional[str]) -> Optional[float]:
        if not text:
            return None
        cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            val = float(cleaned)
            return val if val > 0 else None
        except ValueError:
            return None

    @staticmethod
    def _sum_credits(transactions: list) -> float:
        return round(sum(t["credit"] for t in transactions), 2)

    @staticmethod
    def _sum_debits(transactions: list) -> float:
        return round(sum(t["debit"] for t in transactions), 2)

    def _sort_transactions(self, transactions: list, bank: str) -> list:
        """Attempt to sort transactions chronologically."""
        date_format = BANK_PATTERNS.get(bank, {}).get("date_format")
        if not date_format:
            return transactions

        def parse_date(txn):
            try:
                return datetime.strptime(txn["date"], date_format)
            except Exception:
                return datetime.min

        try:
            return sorted(transactions, key=parse_date)
        except Exception:
            return transactions

    # ------------------------------------------------------------------
    # NEFT/RTGS/UPI category classification
    # ------------------------------------------------------------------

    @staticmethod
    def classify_transaction(description: str) -> str:
        """Classify transaction type from description."""
        desc = description.upper()
        if any(k in desc for k in ["NEFT", "NET BANKING", "IMPS"]):
            return "neft_imps"
        if "RTGS" in desc:
            return "rtgs"
        if "UPI" in desc:
            return "upi"
        if any(k in desc for k in ["ATM", "CASH"]):
            return "cash"
        if any(k in desc for k in ["POS", "SWIPE", "PURCHASE"]):
            return "card"
        if any(k in desc for k in ["EMI", "LOAN", "REPAY"]):
            return "loan_repayment"
        if any(k in desc for k in ["GST", "TDS", "TAX"]):
            return "tax"
        if any(k in desc for k in ["SALARY", "PAYROLL"]):
            return "payroll"
        return "other"
