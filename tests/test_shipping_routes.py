import os
import sys
import unittest
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
os.environ.setdefault("JWT_SECRET", "shipping-route-test-secret-longer-than-thirty-two")

from app.auth_context import AuthContext
from app.database import Base, Company, Customer, CustomerIssue, Employee, Location
from app.main import app
from app.web_sessions import create_employee_session, get_web_db


class ShippingCaseRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add(Company(id="co", name="C", code="SHIPPING", password_hash="x"))
            db.add_all(
                [
                    Location(id="l1", company_id="co", name="Sayville", store_number="5127"),
                    Location(id="l2", company_id="co", name="Selden", store_number="5345"),
                    Employee(
                        id="e",
                        company_id="co",
                        name="Employee",
                        pin_hash="x",
                        role="employee",
                        location_ids=["l1"],
                        auth_version=1,
                    ),
                    Employee(
                        id="a",
                        company_id="co",
                        name="Admin",
                        pin_hash="x",
                        role="admin",
                        location_ids=[],
                        auth_version=1,
                    ),
                    Customer(id="c1", company_id="co", company="Customer One"),
                    Customer(id="c2", company_id="co", company="Customer Two"),
                ]
            )
            db.flush()
            db.add_all(
                [
                    CustomerIssue(
                        id="i1",
                        company_id="co",
                        customer_id="c1",
                        location_id="l1",
                        reference="CI-1",
                        title="Late shipment",
                        description="Details",
                        created_by="e",
                        updated_by="e",
                    ),
                    CustomerIssue(
                        id="i2",
                        company_id="co",
                        customer_id="c2",
                        location_id="l1",
                        reference="CI-2",
                        title="Other customer",
                        description="Details",
                        created_by="e",
                        updated_by="e",
                    ),
                ]
            )
            db.commit()

        def db_dependency():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_web_db] = db_dependency
        self.client = TestClient(app, base_url="https://testserver")
        self.login()

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def login(self, admin=False):
        token, csrf = create_employee_session(
            AuthContext(
                "co",
                "a" if admin else "e",
                "admin" if admin else "employee",
                "l1",
                1,
            )
        )
        self.client.cookies.set("pom_session", token)
        self.headers = {"X-CSRF-Token": csrf}

    def body(self, **changes):
        return {
            "location_id": "l1",
            "customer_id": "c1",
            "customer_issue_id": "i1",
            "tracking_number": "1ZTEST123",
            "carrier": "UPS",
            "service_level": "Next Day Air",
            "case_type": "GSR",
            "status": "Submitted",
            "ship_date": "2026-10-01",
            "promised_date": "2026-10-02",
            "delivered_date": "2026-10-03",
            "carrier_reference": "GSR-123",
            "amount_requested": 42.5,
            "amount_approved": 0,
            "next_action": "Check carrier response",
            "follow_up_date": date(2020, 1, 1).isoformat(),
            "notes": "Late delivery",
        } | changes

    def test_gsr_lifecycle_summary_and_customer_filter(self):
        response = self.client.post(
            "/api/shipping-cases", json=self.body(), headers=self.headers
        )
        self.assertEqual(response.status_code, 201, response.text)
        case = response.json()
        self.assertEqual(case["issue_reference"], "CI-1")
        self.assertEqual(case["tracking_number"], "1ZTEST123")

        summary = self.client.get("/api/shipping-cases/summary").json()
        self.assertEqual(summary["open"], 1)
        self.assertEqual(summary["overdue_followups"], 1)
        self.assertEqual(summary["gsr_pending"], 1)

        filtered = self.client.get(
            "/api/shipping-cases?customer_id=c1&open_only=false"
        ).json()
        self.assertEqual(filtered["total"], 1)

        approved = self.client.patch(
            "/api/shipping-cases/" + case["id"],
            json=self.body(version=1, status="Approved", amount_approved=42.5),
            headers=self.headers,
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["status"], "Approved")
        self.assertEqual(
            self.client.get("/api/shipping-cases/summary").json()["approved"], 1
        )

        refunded = self.client.patch(
            "/api/shipping-cases/" + case["id"],
            json=self.body(
                version=2,
                status="Refunded",
                amount_approved=42.5,
                follow_up_date=None,
            ),
            headers=self.headers,
        )
        self.assertEqual(refunded.status_code, 200, refunded.text)
        self.assertIsNotNone(refunded.json()["resolved_at"])
        self.assertEqual(self.client.get("/api/shipping-cases").json()["total"], 0)

    def test_store_scope_and_link_validation(self):
        self.assertEqual(
            self.client.post(
                "/api/shipping-cases",
                json=self.body(location_id="l2", customer_issue_id=None),
                headers=self.headers,
            ).status_code,
            403,
        )
        mismatch = self.client.post(
            "/api/shipping-cases",
            json=self.body(customer_issue_id="i2"),
            headers=self.headers,
        )
        self.assertEqual(mismatch.status_code, 400)

        self.login(admin=True)
        response = self.client.post(
            "/api/shipping-cases",
            json=self.body(
                location_id="l2",
                customer_issue_id=None,
                tracking_number="1ZOTHER",
            ),
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)

    def test_csrf_and_amount_validation(self):
        self.assertEqual(
            self.client.post("/api/shipping-cases", json=self.body()).status_code,
            403,
        )
        invalid = self.client.post(
            "/api/shipping-cases",
            json=self.body(amount_requested=10, amount_approved=20),
            headers=self.headers,
        )
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
