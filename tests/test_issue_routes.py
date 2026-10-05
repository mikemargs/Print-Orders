import os
import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
os.environ.setdefault("JWT_SECRET", "issue-route-test-secret-longer-than-thirty-two")
from app.auth_context import AuthContext
from app.database import Base, Company, Customer, CustomerIssue, Employee, Location
from app.main import app
from app.web_sessions import create_employee_session, get_web_db


class IssueRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all(
                [
                    Company(id="co", name="C", code="ISSUES", password_hash="x"),
                    Company(id="other", name="O", code="OTHER", password_hash="x"),
                ]
            )
            db.flush()
            db.add_all(
                [
                    Location(
                        id="l",
                        company_id="co",
                        name="Sayville",
                        store_number="5127",
                        timezone="America/New_York",
                    ),
                    Location(id="l2", company_id="co", name="Selden", store_number="5345"),
                    Location(id="f", company_id="other", name="Other", store_number="1"),
                    Employee(
                        id="e",
                        company_id="co",
                        name="Employee",
                        pin_hash="x",
                        role="employee",
                        location_ids=["l"],
                        auth_version=1,
                    ),
                    Employee(
                        id="a",
                        company_id="co",
                        name="Admin",
                        pin_hash="x",
                        role="admin",
                        auth_version=1,
                    ),
                    Customer(id="c", company_id="co", first_name="Test"),
                    Customer(id="fc", company_id="other"),
                ]
            )
            db.commit()

        def db_dependency():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_web_db] = db_dependency
        self.client = TestClient(app, base_url="https://testserver")
        self.login()
        self.body = {
            "customer_id": "c",
            "location_id": "l",
            "title": "Complaint",
            "description": "Details",
        }

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def login(self, admin=False):
        token, csrf = create_employee_session(
            AuthContext("co", "a" if admin else "e", "admin" if admin else "employee", "l", 1)
        )
        self.client.cookies.set("pom_session", token)
        self.headers = {"X-CSRF-Token": csrf}

    def create(self, **change):
        r = self.client.post("/api/issues", json=self.body | change, headers=self.headers)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def test_auth_csrf_and_validation(self):
        self.assertEqual(self.client.post("/api/issues", json=self.body).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/issues", json=self.body | {"priority": "Invalid"}, headers=self.headers
            ).status_code,
            422,
        )
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/issues").status_code, 401)

    def test_case_lifecycle_history_and_conflict(self):
        row = self.create()
        self.assertEqual(self.client.get("/api/issues/" + row["id"]).status_code, 200)
        r = self.client.patch(
            "/api/issues/" + row["id"],
            json={"version": 1, "status": "Resolved", "resolution_summary": "Refund recorded"},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        r = self.client.patch(
            "/api/issues/" + row["id"], json={"version": 1, "title": "Stale"}, headers=self.headers
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["current"]["version"], 2)
        r = self.client.patch(
            "/api/issues/" + row["id"],
            json={"version": 2, "status": "Open", "reopen_reason": "Follow-up needed"},
            headers=self.headers,
        )
        self.assertEqual(r.status_code, 200, r.text)
        log = {
            "operation_id": str(uuid4()),
            "channel": "phone",
            "occurred_at": "2026-10-05T10:00:00-04:00",
            "summary": "Called customer",
        }
        for _ in range(2):
            self.assertEqual(
                self.client.post(
                    "/api/issues/" + row["id"] + "/activities", json=log, headers=self.headers
                ).status_code,
                201,
            )
        history = self.client.get("/api/issues/" + row["id"] + "/activities").json()
        self.assertEqual(history["total"], 4)
        self.assertEqual(
            sum(x["activity_type"] == "communication" for x in history["activities"]), 1
        )

    def test_tenant_isolation_and_active_store(self):
        with self.Session() as db:
            db.add(
                CustomerIssue(
                    id="foreign",
                    company_id="other",
                    customer_id="fc",
                    location_id="f",
                    reference="CI-f",
                    title="Secret",
                    description="Secret",
                    created_by="a",
                    updated_by="a",
                )
            )
            db.commit()
        self.assertEqual(self.client.get("/api/issues/foreign").status_code, 404)
        self.assertEqual(self.client.get("/api/issues/foreign/activities").status_code, 404)
        self.assertEqual(self.client.get("/api/issues").json()["total"], 0)
        self.assertEqual(
            self.client.post(
                "/api/issues", json=self.body | {"location_id": "l2"}, headers=self.headers
            ).status_code,
            403,
        )
        self.login(admin=True)
        row = self.create(location_id="l2")
        self.login()
        self.assertEqual(self.client.get("/api/issues/" + row["id"]).status_code, 200)
        self.assertEqual(
            self.client.patch(
                "/api/issues/" + row["id"],
                json={"version": 1, "title": "Cannot"},
                headers=self.headers,
            ).status_code,
            403,
        )

    def test_complete_summaries_timezone_and_search(self):
        with self.Session() as db:
            for n in range(270):
                db.add(
                    CustomerIssue(
                        id=str(n),
                        company_id="co",
                        customer_id="c",
                        location_id="l",
                        reference="CI-" + str(n),
                        title="100% literal" if n == 0 else "Other",
                        description="D",
                        created_by="e",
                        updated_by="e",
                        follow_up_date=date(2026, 10, 4),
                        priority="High",
                        assigned_employee_id="e",
                    )
                )
            db.add(
                CustomerIssue(
                    id="past",
                    company_id="co",
                    customer_id="c",
                    location_id="l",
                    reference="CI-past",
                    title="Past",
                    description="D",
                    created_by="e",
                    updated_by="e",
                    follow_up_date=date(2026, 10, 3),
                )
            )
            db.add(
                CustomerIssue(
                    id="resolved",
                    company_id="co",
                    customer_id="c",
                    location_id="l",
                    reference="CI-resolved",
                    title="Resolved",
                    description="D",
                    created_by="e",
                    updated_by="e",
                    status="Resolved",
                    follow_up_date=date(2026, 10, 1),
                )
            )
            db.commit()
        with patch("app.routers.issues.utcnow", return_value=datetime(2026, 10, 5, 1, tzinfo=UTC)):
            summary = self.client.get("/api/issues/summary").json()
        self.assertEqual(
            summary, {"open": 271, "overdue": 1, "high_priority": 270, "assigned_to_me": 270}
        )
        result = self.client.get("/api/issues?limit=2").json()
        self.assertEqual(result["total"], 272)
        self.assertEqual(len(result["issues"]), 2)
        self.assertEqual(self.client.get("/api/issues?search=100%25").json()["total"], 1)
        self.assertEqual(self.client.get("/api/issues?search=%25").json()["total"], 1)
