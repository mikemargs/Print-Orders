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
os.environ.setdefault("JWT_SECRET", "task-route-test-secret-longer-than-thirty-two")

from app.auth_context import AuthContext
from app.database import Base, Company, Customer, Employee, Location, WorkOrder
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
            db.add(Company(id="co", name="C", code="TASKS", password_hash="x"))
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
                    Customer(id="c", company_id="co", company="Customer"),
                ]
            )
            db.flush()
            db.add(
                WorkOrder(
                    id="o",
                    company_id="co",
                    customer_id="c",
                    location_id="l1",
                    order_number="WO-1",
                )
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
            AuthContext("co", "a" if admin else "e", "admin" if admin else "employee", "l1", 1)
        )
        self.client.cookies.set("pom_session", token)
        self.headers = {"X-CSRF-Token": csrf}

    def test_task_lifecycle_summary_and_links(self):
        body = {
            "location_id": "l1",
            "title": "Call customer",
            "description": "Confirm artwork",
            "priority": "High",
            "due_date": "2026-10-06",
            "assigned_employee_id": "e",
            "customer_id": "c",
            "work_order_id": "o",
        }
        response = self.client.post("/api/tasks", json=body, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        task = response.json()
        self.assertEqual(task["order_number"], "WO-1")
        self.assertEqual(task["assignee"]["name"], "Employee")

        listed = self.client.get("/api/tasks").json()
        self.assertEqual(listed["total"], 1)
        self.assertEqual(listed["tasks"][0]["title"], "Call customer")

        summary = self.client.get("/api/tasks/summary").json()
        self.assertEqual(summary["open"], 1)
        self.assertEqual(summary["high_priority"], 1)
        self.assertEqual(summary["assigned_to_me"], 1)

        update_body = body | {"version": 1, "status": "Completed"}
        updated = self.client.patch(
            "/api/tasks/" + task["id"], json=update_body, headers=self.headers
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["status"], "Completed")
        self.assertIsNotNone(updated.json()["completed_at"])
        self.assertEqual(self.client.get("/api/tasks").json()["total"], 0)

    def test_customer_filter_only_returns_linked_tasks(self):
        first = self.client.post(
            "/api/tasks",
            json={"location_id": "l1", "title": "Customer task", "customer_id": "c"},
            headers=self.headers,
        )
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post(
            "/api/tasks",
            json={"location_id": "l1", "title": "General task"},
            headers=self.headers,
        )
        self.assertEqual(second.status_code, 201, second.text)
        filtered = self.client.get("/api/tasks?customer_id=c&open_only=false").json()
        self.assertEqual(filtered["total"], 1)
        self.assertEqual(filtered["tasks"][0]["title"], "Customer task")

    def test_store_scope_and_csrf(self):
        body = {"location_id": "l2", "title": "Other store task"}
        self.assertEqual(self.client.post("/api/tasks", json=body).status_code, 403)
        self.assertEqual(
            self.client.post("/api/tasks", json=body, headers=self.headers).status_code, 403
        )
        self.login(admin=True)
        response = self.client.post("/api/tasks", json=body, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)

    def test_overdue_summary(self):
        body = {
            "location_id": "l1",
            "title": "Past due",
            "due_date": date(2020, 1, 1).isoformat(),
            "priority": "Urgent",
        }
        self.assertEqual(
            self.client.post("/api/tasks", json=body, headers=self.headers).status_code, 201
        )
        summary = self.client.get("/api/tasks/summary").json()
        self.assertEqual(summary["overdue"], 1)
        self.assertEqual(summary["high_priority"], 1)


if __name__ == "__main__":
    unittest.main()
