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
os.environ.setdefault("JWT_SECRET", "operations-route-test-secret-longer-than-thirty-two")

from app.auth_context import AuthContext
from app.database import Base, Company, Employee, Location
from app.main import app
from app.web_sessions import create_employee_session, get_web_db


class OperationsRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        Base.metadata.create_all(self.engine)
        with self.Session() as db:
            db.add(Company(id="co", name="Company", code="OPS", password_hash="x"))
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
                        id="s",
                        company_id="co",
                        name="Supervisor",
                        pin_hash="x",
                        role="supervisor",
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
                ]
            )
            db.commit()

        def db_dependency():
            with self.Session() as db:
                yield db

        app.dependency_overrides[get_web_db] = db_dependency
        self.client = TestClient(app, base_url="https://testserver")
        self.login("s", "supervisor", "l1")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.engine.dispose()

    def login(self, employee_id, role, location_id):
        token, csrf = create_employee_session(
            AuthContext("co", employee_id, role, location_id, 1)
        )
        self.client.cookies.set("pom_session", token)
        self.headers = {"X-CSRF-Token": csrf}

    def template_body(self, **changes):
        base = {
            "location_id": "l1",
            "title": "Open registers",
            "description": "Verify front counter is ready",
            "category": "Opening",
            "active_days": [0, 1, 2, 3, 4, 5, 6],
            "required": True,
            "active": True,
            "sort_order": 10,
        }
        return base | changes

    def create_template(self, **changes):
        response = self.client.post(
            "/api/operations/templates",
            json=self.template_body(**changes),
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_template_completion_reset_and_summary(self):
        template = self.create_template()
        target = date.today().isoformat()

        checklist = self.client.get(
            "/api/operations/checklist",
            params={"location_id": "l1", "checklist_date": target},
        )
        self.assertEqual(checklist.status_code, 200, checklist.text)
        self.assertEqual(len(checklist.json()["items"]), 1)
        self.assertIsNone(checklist.json()["items"][0]["completion"])

        self.login("e", "employee", "l1")
        response = self.client.put(
            f"/api/operations/checklist/{template['id']}",
            json={"checklist_date": target, "status": "Completed", "notes": "Done"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        completion = response.json()["completion"]
        self.assertEqual(completion["status"], "Completed")
        self.assertEqual(completion["completed_by_name"], "Employee")

        summary = self.client.get("/api/operations/summary").json()
        self.assertEqual(summary["expected"], 1)
        self.assertEqual(summary["completed"], 1)
        self.assertEqual(summary["pending"], 0)
        self.assertEqual(summary["required_pending"], 0)

        reset = self.client.delete(
            f"/api/operations/checklist/{template['id']}",
            params={"checklist_date": target},
            headers=self.headers,
        )
        self.assertEqual(reset.status_code, 204, reset.text)
        summary = self.client.get("/api/operations/summary").json()
        self.assertEqual(summary["pending"], 1)
        self.assertEqual(summary["required_pending"], 1)

    def test_template_management_requires_supervisor_and_active_store(self):
        self.login("e", "employee", "l1")
        self.assertEqual(
            self.client.post(
                "/api/operations/templates",
                json=self.template_body(),
                headers=self.headers,
            ).status_code,
            403,
        )

        self.login("s", "supervisor", "l1")
        self.assertEqual(
            self.client.post(
                "/api/operations/templates",
                json=self.template_body(location_id="l2"),
                headers=self.headers,
            ).status_code,
            403,
        )

        self.login("a", "admin", "l1")
        response = self.client.post(
            "/api/operations/templates",
            json=self.template_body(location_id="l2", title="Selden close"),
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 201, response.text)

    def test_weekday_schedule_and_version_conflict(self):
        weekday = date.today().weekday()
        other_day = (weekday + 1) % 7
        template = self.create_template(active_days=[weekday])

        visible = self.client.get(
            "/api/operations/checklist",
            params={"location_id": "l1", "checklist_date": date.today().isoformat()},
        ).json()
        self.assertEqual(len(visible["items"]), 1)

        updated = self.client.patch(
            f"/api/operations/templates/{template['id']}",
            json=self.template_body(
                version=template["version"],
                active_days=[other_day],
            ),
            headers=self.headers,
        )
        self.assertEqual(updated.status_code, 200, updated.text)

        stale = self.client.patch(
            f"/api/operations/templates/{template['id']}",
            json=self.template_body(version=template["version"]),
            headers=self.headers,
        )
        self.assertEqual(stale.status_code, 409)


if __name__ == "__main__":
    unittest.main()
