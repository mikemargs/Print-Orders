import os
import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
os.environ.setdefault("JWT_SECRET", "task-route-test-secret-longer-than-thirty-two")

from app.auth_context import AuthContext
from app.database import (
    Base,
    Company,
    Customer,
    CustomerIssue,
    Employee,
    Location,
    OperationsTask,
    WorkOrder,
)
from app.main import app
from app.web_sessions import create_employee_session, get_web_db


class TaskRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add_all(
                [
                    Company(id="co", name="C", code="TASKS", password_hash="x"),
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
                    Location(
                        id="l2",
                        company_id="co",
                        name="Selden",
                        store_number="5345",
                        timezone="America/New_York",
                    ),
                    Location(
                        id="f",
                        company_id="other",
                        name="Other",
                        store_number="1",
                    ),
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
                        id="e2",
                        company_id="co",
                        name="Selden Employee",
                        pin_hash="x",
                        role="employee",
                        location_ids=["l2"],
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
            db.flush()
            db.add(
                WorkOrder(
                    id="o",
                    company_id="co",
                    customer_id="c",
                    location_id="l",
                    order_number="WO-1",
                )
            )
            db.add(
                CustomerIssue(
                    id="i",
                    company_id="co",
                    customer_id="c",
                    location_id="l",
                    reference="CI-1",
                    title="Issue",
                    description="Details",
                    created_by="e",
                    updated_by="e",
                )
            )
            db.commit()

        def db_dependency():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_web_db] = db_dependency
        self.client = TestClient(app, base_url="https://testserver")
        self.login()
        self.body = {
            "location_id": "l",
            "title": "Call customer",
            "description": "Confirm artwork approval",
            "priority": "High",
            "assigned_employee_id": "e",
            "due_date": "2026-10-06",
            "customer_id": "c",
            "work_order_id": "o",
            "issue_id": "i",
        }

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def login(self, admin=False, location_id="l"):
        token, csrf = create_employee_session(
            AuthContext(
                "co",
                "a" if admin else "e",
                "admin" if admin else "employee",
                location_id,
                1,
            )
        )
        self.client.cookies.set("pom_session", token)
        self.headers = {"X-CSRF-Token": csrf}

    def create(self, **change):
        response = self.client.post(
            "/api/tasks", json=self.body | change, headers=self.headers
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_task_lifecycle_list_and_conflict(self):
        row = self.create()
        self.assertEqual(row["status"], "Open")
        self.assertEqual(row["order"]["order_number"], "WO-1")
        self.assertEqual(row["issue"]["reference"], "CI-1")

        listing = self.client.get("/api/tasks?open_only=true").json()
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["tasks"][0]["id"], row["id"])

        completed = self.client.patch(
            "/api/tasks/" + row["id"],
            json={"version": 1, "status": "Completed"},
            headers=self.headers,
        )
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual(completed.json()["version"], 2)
        self.assertIsNotNone(completed.json()["completed_at"])
        self.assertEqual(self.client.get("/api/tasks?open_only=true").json()["total"], 0)

        stale = self.client.patch(
            "/api/tasks/" + row["id"],
            json={"version": 1, "title": "Stale"},
            headers=self.headers,
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["current"]["version"], 2)

        reopened = self.client.patch(
            "/api/tasks/" + row["id"],
            json={"version": 2, "status": "Open"},
            headers=self.headers,
        )
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertIsNone(reopened.json()["completed_at"])

    def test_tenant_isolation_active_store_and_assignment_validation(self):
        with self.Session() as db:
            db.add(
                OperationsTask(
                    id="foreign",
                    company_id="other",
                    location_id="f",
                    title="Secret",
                    created_by="x",
                    updated_by="x",
                )
            )
            db.commit()
        self.assertEqual(self.client.get("/api/tasks/foreign").status_code, 404)
        self.assertEqual(self.client.get("/api/tasks").json()["total"], 0)

        wrong_store = self.client.post(
            "/api/tasks",
            json=self.body | {"location_id": "l2", "work_order_id": None, "issue_id": None},
            headers=self.headers,
        )
        self.assertEqual(wrong_store.status_code, 403)

        wrong_assignee = self.client.post(
            "/api/tasks",
            json=self.body | {"assigned_employee_id": "e2"},
            headers=self.headers,
        )
        self.assertEqual(wrong_assignee.status_code, 400)

        self.login(admin=True)
        row = self.create(
            location_id="l2",
            customer_id=None,
            work_order_id=None,
            issue_id=None,
            assigned_employee_id="e2",
        )
        self.login()
        self.assertEqual(self.client.get("/api/tasks/" + row["id"]).status_code, 200)
        denied = self.client.patch(
            "/api/tasks/" + row["id"],
            json={"version": 1, "title": "Cannot change"},
            headers=self.headers,
        )
        self.assertEqual(denied.status_code, 403)

    def test_summary_search_and_due_dates(self):
        with self.Session() as db:
            db.add_all(
                [
                    OperationsTask(
                        id="overdue",
                        company_id="co",
                        location_id="l",
                        title="100% follow-up",
                        status="Open",
                        priority="Urgent",
                        assigned_employee_id="e",
                        due_date=date(2026, 10, 5),
                        created_by="e",
                        updated_by="e",
                    ),
                    OperationsTask(
                        id="today",
                        company_id="co",
                        location_id="l",
                        title="Today",
                        status="In Progress",
                        due_date=date(2026, 10, 6),
                        created_by="e",
                        updated_by="e",
                    ),
                    OperationsTask(
                        id="done",
                        company_id="co",
                        location_id="l",
                        title="Done",
                        status="Completed",
                        due_date=date(2026, 10, 1),
                        created_by="e",
                        updated_by="e",
                    ),
                ]
            )
            db.commit()

        from unittest.mock import patch

        with patch(
            "app.routers.tasks.utcnow",
            return_value=datetime(2026, 10, 6, 16, tzinfo=UTC),
        ):
            summary = self.client.get("/api/tasks/summary").json()
        self.assertEqual(
            summary,
            {"open": 2, "overdue": 1, "due_today": 1, "assigned_to_me": 1},
        )
        self.assertEqual(self.client.get("/api/tasks?search=100%25").json()["total"], 1)
        self.assertEqual(self.client.get("/api/tasks?search=%25").json()["total"], 1)


if __name__ == "__main__":
    unittest.main()
