import os
import sys
import unittest
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
            db.flush()
            db.add_all([
                Location(id="l", company_id="co", name="Sayville", store_number="5127"),
                Location(id="l2", company_id="co", name="Selden", store_number="5345"),
                Employee(id="e", company_id="co", name="Employee", pin_hash="x", role="employee", location_ids=["l"], auth_version=1),
                Employee(id="e2", company_id="co", name="Selden Employee", pin_hash="x", role="employee", location_ids=["l2"], auth_version=1),
                Employee(id="a", company_id="co", name="Admin", pin_hash="x", role="admin", auth_version=1),
                Customer(id="c", company_id="co", first_name="Customer"),
            ])
            db.flush()
            db.add(WorkOrder(id="o", company_id="co", customer_id="c", location_id="l", order_number="WO-1"))
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
            AuthContext("co", "a" if admin else "e", "admin" if admin else "employee", "l", 1)
        )
        self.client.cookies.set("pom_session", token)
        self.headers = {"X-CSRF-Token": csrf}

    def create(self, **change):
        body = {"location_id": "l", "title": "Call customer", "priority": "High"} | change
        response = self.client.post("/api/tasks", json=body, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_list_summary_and_complete(self):
        row = self.create(due_date="2020-01-01", assigned_employee_id="e", work_order_id="o", customer_id="c")
        self.assertEqual(row["store"]["store_number"], "5127")
        self.assertEqual(row["assignee"]["name"], "Employee")
        listed = self.client.get("/api/tasks?open_only=true").json()
        self.assertEqual(listed["total"], 1)
        summary = self.client.get("/api/tasks/summary").json()
        self.assertEqual(summary["open"], 1)
        self.assertEqual(summary["overdue"], 1)
        self.assertEqual(summary["assigned_to_me"], 1)
        done = self.client.patch(
            "/api/tasks/" + row["id"],
            json={"version": row["version"], "status": "Completed"},
            headers=self.headers,
        )
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(done.json()["status"], "Completed")
        self.assertIsNotNone(done.json()["completed_at"])
        self.assertEqual(self.client.get("/api/tasks?open_only=true").json()["total"], 0)

    def test_store_write_scope_and_assignee_eligibility(self):
        response = self.client.post(
            "/api/tasks",
            json={"location_id": "l2", "title": "Wrong store"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            "/api/tasks",
            json={"location_id": "l", "title": "Wrong employee", "assigned_employee_id": "e2"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.login(admin=True)
        response = self.client.post(
            "/api/tasks",
            json={"location_id": "l2", "title": "Admin cross-store", "assigned_employee_id": "e2"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)

    def test_conflict_and_csrf(self):
        row = self.create()
        self.assertEqual(self.client.post("/api/tasks", json={"location_id": "l", "title": "No csrf"}).status_code, 403)
        first = self.client.patch(
            "/api/tasks/" + row["id"],
            json={"version": 1, "status": "In Progress"},
            headers=self.headers,
        )
        self.assertEqual(first.status_code, 200, first.text)
        stale = self.client.patch(
            "/api/tasks/" + row["id"],
            json={"version": 1, "status": "Waiting"},
            headers=self.headers,
        )
        self.assertEqual(stale.status_code, 409)


if __name__ == "__main__":
    unittest.main()
