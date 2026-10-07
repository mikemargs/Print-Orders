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
os.environ.setdefault("JWT_SECRET", "mailbox-route-test-secret-longer-than-thirty-two")

from app.auth_context import AuthContext
from app.database import Base, Company, Customer, Employee, Location
from app.main import app
from app.web_sessions import create_employee_session, get_web_db


class MailboxRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add(Company(id="co", name="C", code="MAILBOX", password_hash="x"))
            db.add_all(
                [
                    Location(
                        id="l1",
                        company_id="co",
                        name="Sayville",
                        store_number="5127",
                        timezone="America/New_York",
                    ),
                    Location(
                        id="l2",
                        company_id="co",
                        name="Selden",
                        store_number="5345",
                        timezone="America/New_York",
                    ),
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
            "mailbox_number": "101",
            "status": "Active",
            "renewal_date": date(2020, 1, 1).isoformat(),
            "balance_due": 25.5,
            "primary_id_on_file": False,
            "secondary_id_on_file": False,
            "form_1583_complete": False,
            "msa_complete": False,
            "phone_verified": False,
            "forwarding_status": "None",
            "forwarding_address": "",
            "notes": "Follow up",
        } | changes

    def test_mailbox_lifecycle_summary_and_compliance(self):
        response = self.client.post(
            "/api/mailboxes", json=self.body(), headers=self.headers
        )
        self.assertEqual(response.status_code, 201, response.text)
        mailbox = response.json()
        self.assertGreater(mailbox["days_overdue"], 0)
        self.assertFalse(mailbox["compliance_complete"])
        self.assertIn("USPS Form 1583", mailbox["missing_compliance"])

        summary = self.client.get("/api/mailboxes/summary").json()
        self.assertEqual(summary["active"], 1)
        self.assertEqual(summary["overdue"], 1)
        self.assertEqual(summary["missing_compliance"], 1)

        update_body = self.body(
            version=1,
            status="Blocked",
            primary_id_on_file=True,
            secondary_id_on_file=True,
            form_1583_complete=True,
            msa_complete=True,
            phone_verified=True,
        )
        updated = self.client.patch(
            "/api/mailboxes/" + mailbox["id"],
            json=update_body,
            headers=self.headers,
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertTrue(updated.json()["compliance_complete"])
        self.assertEqual(updated.json()["status"], "Blocked")
        summary = self.client.get("/api/mailboxes/summary").json()
        self.assertEqual(summary["blocked"], 1)
        self.assertEqual(summary["missing_compliance"], 0)

    def test_duplicate_number_customer_filter_and_scope(self):
        first = self.client.post(
            "/api/mailboxes", json=self.body(), headers=self.headers
        )
        self.assertEqual(first.status_code, 201, first.text)
        duplicate = self.client.post(
            "/api/mailboxes",
            json=self.body(customer_id="c2"),
            headers=self.headers,
        )
        self.assertEqual(duplicate.status_code, 409)

        filtered = self.client.get("/api/mailboxes?customer_id=c1").json()
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["mailboxes"][0]["mailbox_number"], "101")

        other_store = self.client.post(
            "/api/mailboxes",
            json=self.body(location_id="l2", mailbox_number="101"),
            headers=self.headers,
        )
        self.assertEqual(other_store.status_code, 403)

        self.login(admin=True)
        other_store = self.client.post(
            "/api/mailboxes",
            json=self.body(location_id="l2", mailbox_number="101"),
            headers=self.headers,
        )
        self.assertEqual(other_store.status_code, 201, other_store.text)

    def test_csrf_and_forwarding_validation(self):
        self.assertEqual(
            self.client.post("/api/mailboxes", json=self.body()).status_code,
            403,
        )
        invalid = self.client.post(
            "/api/mailboxes",
            json=self.body(
                mailbox_number="102",
                forwarding_status="Active",
                forwarding_address="",
            ),
            headers=self.headers,
        )
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
