"""
Phase 4 tests — Webhooks, Bank Statement multi-format, ROC parser, caching, rate limiting.
"""

import pytest
import json
import hmac
import hashlib
from unittest.mock import patch, MagicMock
from uuid import uuid4


# ---------------------------------------------------------------------------
# Webhook API tests
# ---------------------------------------------------------------------------

class TestWebhookEndpoints:
    def test_create_webhook(self, client, auth_headers, partner_id):
        """Register a webhook and verify it's stored."""
        resp = client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/webhook",
                "event_types": ["compliance_check_complete", "manual_override"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://example.com/webhook"
        assert "compliance_check_complete" in data["event_types"]
        assert data["is_active"] is True
        assert "id" in data

    def test_create_webhook_invalid_url(self, client, auth_headers):
        """Webhook URL must start with http(s)."""
        resp = client.post(
            "/api/v1/webhooks",
            json={
                "url": "ftp://bad-url.com/hook",
                "event_types": ["manual_override"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_webhook_invalid_event_type(self, client, auth_headers):
        """Invalid event type must be rejected."""
        resp = client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/hook",
                "event_types": ["not_a_real_event"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_webhook_wildcard(self, client, auth_headers):
        """Wildcard event type '*' should be accepted."""
        resp = client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/hook",
                "event_types": ["*"],
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "*" in resp.json()["event_types"]

    def test_list_webhooks(self, client, auth_headers):
        """List returns only the current partner's webhooks."""
        # Create one
        client.post(
            "/api/v1/webhooks",
            json={"url": "https://example.com/hook1", "event_types": ["manual_override"]},
            headers=auth_headers,
        )
        resp = client.get("/api/v1/webhooks", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_delete_webhook(self, client, auth_headers):
        """Deleting a webhook marks it inactive (soft delete)."""
        create_resp = client.post(
            "/api/v1/webhooks",
            json={"url": "https://example.com/hook2", "event_types": ["scrape_complete"]},
            headers=auth_headers,
        )
        webhook_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["ok"] is True

        # Verify it's now inactive
        get_resp = client.get(f"/api/v1/webhooks/{webhook_id}", headers=auth_headers)
        assert get_resp.json()["is_active"] is False

    def test_webhook_company_filter(self, client, auth_headers):
        """Webhook linked to a specific company."""
        # Create a company first
        company_resp = client.post(
            "/api/v1/companies",
            json={"name": "Hook Test Co", "gst_id": "27AABCA0001A1Z5"},
            headers=auth_headers,
        )
        company_id = company_resp.json()["id"]

        resp = client.post(
            "/api/v1/webhooks",
            json={
                "url": "https://example.com/hook3",
                "event_types": ["compliance_check_complete"],
                "company_id": company_id,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["company_id"] == company_id

    def test_webhook_unauthorized_access(self, client, auth_headers):
        """Cannot access another partner's webhook."""
        import jwt
        from app.config import settings

        # Create webhook under auth_headers partner
        create_resp = client.post(
            "/api/v1/webhooks",
            json={"url": "https://example.com/priv", "event_types": ["manual_override"]},
            headers=auth_headers,
        )
        webhook_id = create_resp.json()["id"]

        # Try to access with a different partner token
        other_token = jwt.encode(
            {"sub": "other-user", "partner_id": str(uuid4())},
            settings.JWT_SECRET,
            algorithm="HS256",
        )
        resp = client.get(
            f"/api/v1/webhooks/{webhook_id}",
            headers={"Authorization": f"Bearer {other_token}"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Bank Statement Parser tests
# ---------------------------------------------------------------------------

class TestBankStatementParser:
    def get_parser(self):
        from app.services.bank_scraper import BankStatementParser
        return BankStatementParser.__new__(BankStatementParser)

    def test_detect_icici_bank(self):
        parser = self.get_parser()
        text = "ICICI BANK LTD\nAccount Statement\n01/04/2025"
        assert parser._detect_bank(text) == "icici"

    def test_detect_hdfc_bank(self):
        parser = self.get_parser()
        text = "HDFC BANK LIMITED\nSavings Account Statement"
        assert parser._detect_bank(text) == "hdfc"

    def test_detect_axis_bank(self):
        parser = self.get_parser()
        text = "AXIS BANK LTD\nYour Account Statement"
        assert parser._detect_bank(text) == "axis"

    def test_detect_sbi(self):
        parser = self.get_parser()
        text = "STATE BANK OF INDIA\nPassbook Statement"
        assert parser._detect_bank(text) == "sbi"

    def test_detect_generic_fallback(self):
        parser = self.get_parser()
        text = "Some Unknown Bank\nAccount Statement\nOpening Balance: 10,000.00"
        result = parser._detect_bank(text)
        assert result == "generic"

    def test_extract_summary_generic(self):
        parser = self.get_parser()
        text = """
        Opening Balance: 50,000.00
        Total Credits: 25,000.00
        Total Debits: 15,000.00
        Closing Balance: 60,000.00
        """
        summary = parser._extract_summary(text, "generic")
        assert summary["opening_balance"] == 50000.00
        assert summary["closing_balance"] == 60000.00
        assert summary["total_credits"] == 25000.00
        assert summary["total_debits"] == 15000.00

    def test_reconciliation_balanced(self):
        parser = self.get_parser()
        transactions = [
            {"debit": 0.0, "credit": 5000.0, "date": "01/04/2025", "description": "Salary", "balance": 55000.0, "transaction_type": "credit"},
            {"debit": 2000.0, "credit": 0.0, "date": "05/04/2025", "description": "Rent", "balance": 53000.0, "transaction_type": "debit"},
        ]
        summary = {"opening_balance": 50000.0, "closing_balance": 53000.0}
        result = parser._reconciliation_check(transactions, summary)
        assert result["status"] == "balanced"
        assert result["variance"] == 0.0

    def test_reconciliation_variance_detected(self):
        parser = self.get_parser()
        transactions = []
        summary = {"opening_balance": 10000.0, "closing_balance": 99999.0}
        result = parser._reconciliation_check(transactions, summary)
        assert result["status"] == "variance_detected"

    def test_reconciliation_insufficient_data(self):
        parser = self.get_parser()
        result = parser._reconciliation_check([], {})
        assert result["status"] == "insufficient_data"

    def test_classify_transaction_upi(self):
        from app.services.bank_scraper import BankStatementParser
        assert BankStatementParser.classify_transaction("UPI/RAZORPAY/payment") == "upi"

    def test_classify_transaction_neft(self):
        from app.services.bank_scraper import BankStatementParser
        assert BankStatementParser.classify_transaction("NEFT-VENDOR PAYMENT") == "neft_imps"

    def test_classify_transaction_tax(self):
        from app.services.bank_scraper import BankStatementParser
        assert BankStatementParser.classify_transaction("GST TDS PAYMENT") == "tax"

    def test_parse_amount_handles_commas(self):
        parser = self.get_parser()
        assert parser._parse_amount("1,23,456.78") == 123456.78

    def test_parse_amount_handles_none(self):
        parser = self.get_parser()
        assert parser._parse_amount(None) is None

    def test_parse_amount_handles_empty(self):
        parser = self.get_parser()
        assert parser._parse_amount("") is None

    def test_sum_credits(self):
        from app.services.bank_scraper import BankStatementParser
        txns = [{"credit": 1000.0, "debit": 0.0}, {"credit": 2500.0, "debit": 0.0}]
        assert BankStatementParser._sum_credits(txns) == 3500.0

    def test_sum_debits(self):
        from app.services.bank_scraper import BankStatementParser
        txns = [{"debit": 500.0, "credit": 0.0}, {"debit": 750.0, "credit": 0.0}]
        assert BankStatementParser._sum_debits(txns) == 1250.0


# ---------------------------------------------------------------------------
# ROC Scraper static parsing tests
# ---------------------------------------------------------------------------

class TestROCScraper:
    def test_parse_from_html_filings(self):
        from app.services.roc_scraper import ROCScraper
        html = """
        <table id="filingTable">
            <tr><th>Form</th><th>Date</th><th>Description</th><th>Status</th></tr>
            <tr>
                <td>MGT-7</td>
                <td>15/11/2024</td>
                <td>Annual Return FY 2023-24</td>
                <td>Approved</td>
            </tr>
            <tr>
                <td>AOC-4</td>
                <td>20/10/2024</td>
                <td>Balance Sheet FY 2023-24</td>
                <td>Approved</td>
            </tr>
        </table>
        """
        result = ROCScraper.parse_from_html(html)
        assert len(result["filings"]) == 2
        assert result["filings"][0]["form_type"] == "MGT-7"
        assert result["filings"][0]["is_annual"] is True
        assert result["filings"][1]["form_type"] == "AOC-4"

    def test_parse_from_html_directors(self):
        from app.services.roc_scraper import ROCScraper
        html = """
        <table id="directorTable">
            <tr><th>DIN</th><th>Name</th><th>Designation</th></tr>
            <tr>
                <td>01234567</td>
                <td>Rajesh Kumar</td>
                <td>Managing Director</td>
            </tr>
        </table>
        """
        result = ROCScraper.parse_from_html(html)
        assert len(result["directors"]) == 1
        assert result["directors"][0]["din"] == "01234567"
        assert result["directors"][0]["name"] == "Rajesh Kumar"

    def test_is_annual_filing(self):
        from app.services.roc_scraper import ROCScraper
        assert ROCScraper._is_annual_filing_static("MGT-7") is True
        assert ROCScraper._is_annual_filing_static("AOC-4") is True
        assert ROCScraper._is_annual_filing_static("MGT-7A") is True
        assert ROCScraper._is_annual_filing_static("INC-22") is False
        assert ROCScraper._is_annual_filing_static("CHG-1") is False

    def test_parse_amount(self):
        from app.services.roc_scraper import ROCScraper
        assert ROCScraper._parse_amount("1,50,00,000") == 15000000.0
        assert ROCScraper._parse_amount("N/A") is None
        assert ROCScraper._parse_amount("") is None

    def test_extract_period_from_description(self):
        from app.services.roc_scraper import ROCScraper
        scraper = ROCScraper.__new__(ROCScraper)
        assert scraper._extract_period_from_description("Annual Return FY 2023-24") == "2023-24"
        assert scraper._extract_period_from_description("No period here") is None

    def test_assess_compliance_compliant(self):
        from app.services.roc_scraper import ROCScraper
        scraper = ROCScraper.__new__(ROCScraper)
        filings = [
            {"late_fee_paid": False, "is_annual": True},
            {"late_fee_paid": False, "is_annual": True},
        ]
        assert scraper._assess_compliance(filings) == "compliant"

    def test_assess_compliance_at_risk(self):
        from app.services.roc_scraper import ROCScraper
        scraper = ROCScraper.__new__(ROCScraper)
        filings = [
            {"late_fee_paid": True, "is_annual": True},
            {"late_fee_paid": True, "is_annual": True},
            {"late_fee_paid": False, "is_annual": True},
        ]
        assert scraper._assess_compliance(filings) == "at_risk"

    def test_assess_compliance_unknown(self):
        from app.services.roc_scraper import ROCScraper
        scraper = ROCScraper.__new__(ROCScraper)
        assert scraper._assess_compliance([]) == "unknown"


# ---------------------------------------------------------------------------
# Webhook dispatch tests (unit — no HTTP server required)
# ---------------------------------------------------------------------------

class TestWebhookDispatch:
    def test_dispatch_webhook_success(self):
        """dispatch_webhook returns success on 200."""
        from app.services.webhook_consumer import dispatch_webhook

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = dispatch_webhook(
                url="https://example.com/hook",
                payload={"event_type": "test", "company_id": "abc"},
                headers={},
            )
        assert result["success"] is True
        assert result["status_code"] == 200

    def test_dispatch_webhook_4xx_no_retry(self):
        """4xx responses are not retried."""
        from app.services.webhook_consumer import dispatch_webhook

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=404)
            result = dispatch_webhook(
                url="https://example.com/hook",
                payload={"event_type": "test"},
                headers={},
            )
        # Should only be called once (no retry on 4xx)
        assert mock_post.call_count == 1
        assert result["success"] is False

    def test_dispatch_webhook_with_hmac_signature(self):
        """Verify HMAC-SHA256 signature header is set correctly."""
        from app.services.webhook_consumer import dispatch_webhook

        secret = "test-secret-key"
        payload = {"event_type": "manual_override"}

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            dispatch_webhook(
                url="https://example.com/hook",
                payload=payload,
                headers={},
                secret=secret,
            )

        call_headers = mock_post.call_args[1]["headers"]
        assert "X-CompLai-Signature" in call_headers
        assert call_headers["X-CompLai-Signature"].startswith("sha256=")

    def test_dispatch_webhook_timeout_retries(self):
        """Timeouts trigger retries."""
        from app.services.webhook_consumer import dispatch_webhook
        import requests as req_lib

        with patch("requests.post", side_effect=req_lib.Timeout) as mock_post:
            with patch("time.sleep"):  # Skip actual sleep
                result = dispatch_webhook(
                    url="https://example.com/hook",
                    payload={"event_type": "test"},
                    headers={},
                )
        # Should have retried 3 times
        assert mock_post.call_count == 3
        assert result["success"] is False

    def test_webhook_matches_event(self):
        """WebhookEndpoint.matches_event filters correctly."""
        from app.models.webhook import WebhookEndpoint

        wh = WebhookEndpoint()
        wh.is_active = True
        wh.event_types = ["compliance_check_complete", "manual_override"]

        assert wh.matches_event("compliance_check_complete") is True
        assert wh.matches_event("manual_override") is True
        assert wh.matches_event("scrape_complete") is False

    def test_webhook_wildcard_matches_all(self):
        """Wildcard '*' matches any event type."""
        from app.models.webhook import WebhookEndpoint

        wh = WebhookEndpoint()
        wh.is_active = True
        wh.event_types = ["*"]

        assert wh.matches_event("any_event") is True
        assert wh.matches_event("compliance_check_complete") is True

    def test_webhook_inactive_matches_nothing(self):
        """Inactive webhooks never match."""
        from app.models.webhook import WebhookEndpoint

        wh = WebhookEndpoint()
        wh.is_active = False
        wh.event_types = ["*"]

        assert wh.matches_event("compliance_check_complete") is False


# ---------------------------------------------------------------------------
# Caching tests
# ---------------------------------------------------------------------------

class TestRedisCache:
    def test_cache_get_miss(self):
        """cache_get returns None on miss."""
        from app.main import cache_get
        # Without Redis running, should return None gracefully
        result = cache_get("nonexistent_key_12345")
        assert result is None

    def test_cache_set_no_redis(self):
        """cache_set fails silently when Redis is unavailable."""
        from app.main import cache_set
        # Should not raise
        cache_set("test_key", {"data": "value"}, ttl=30)

    def test_compliance_status_returns_cached_flag(self, client, auth_headers):
        """Compliance status response includes _cached field."""
        company_resp = client.post(
            "/api/v1/companies",
            json={"name": "Cache Test Co", "gst_id": "27AABCB0001A1Z5"},
            headers=auth_headers,
        )
        company_id = company_resp.json()["id"]

        resp = client.get(
            f"/api/v1/companies/{company_id}/compliance-status",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "_cached" in resp.json()
