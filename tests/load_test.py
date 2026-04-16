"""
Locust load testing for CompLai API.

Usage:
    pip install locust
    locust -f tests/load_test.py --host=http://localhost:8000

Open http://localhost:8089 to configure and run load test.
"""

from locust import HttpUser, task, between
from uuid import uuid4
import json


class CompLaiPartner(HttpUser):
    """Simulates a CS partner using the CompLai API."""

    wait_time = between(1, 3)

    def on_start(self):
        """Get auth token on startup."""
        self.partner_id = str(uuid4())
        self.user_id = str(uuid4())
        resp = self.client.post("/token", json={
            "partner_id": self.partner_id,
            "user_id": self.user_id,
        })
        self.token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.company_ids = []

    @task(3)
    def list_companies(self):
        self.client.get("/api/v1/companies", headers=self.headers)

    @task(2)
    def create_company(self):
        gst_suffix = str(uuid4())[:4].upper()
        resp = self.client.post(
            "/api/v1/companies",
            json={
                "name": f"Load Test Co {gst_suffix}",
                "gst_id": f"27AABAA{gst_suffix[:4].ljust(4, '0')}A1Z5",
            },
            headers=self.headers,
        )
        if resp.status_code == 200:
            self.company_ids.append(resp.json()["id"])

    @task(2)
    def get_compliance_status(self):
        if self.company_ids:
            company_id = self.company_ids[-1]
            self.client.get(
                f"/api/v1/companies/{company_id}/compliance-status",
                headers=self.headers,
            )

    @task(1)
    def get_audit_log(self):
        if self.company_ids:
            company_id = self.company_ids[-1]
            self.client.get(
                f"/api/v1/companies/{company_id}/audit-log",
                headers=self.headers,
            )

    @task(1)
    def health_check(self):
        self.client.get("/health")
