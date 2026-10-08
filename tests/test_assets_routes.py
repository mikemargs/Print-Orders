import os
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
os.environ.setdefault("JWT_SECRET", "asset-route-test-secret-longer-than-thirty-two")

from app.auth_context import AuthContext
from app.database import Base, Company, Employee, Location
from app.main import app
from app.web_sessions import create_employee_session, get_web_db


class AssetRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        with self.Session() as db:
            db.add(Company(id="co", name="Company", code="ASSET", password_hash="x"))
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

    def inventory_body(self, **changes):
        base = {
            "location_id": "l1",
            "name": "24 lb paper",
            "sku": "PAPER-24",
            "category": "Paper",
            "unit": "ream",
            "quantity": 10,
            "reorder_point": 3,
            "target_stock": 12,
            "cost_per_unit": 6.5,
            "vendor": "Paper Vendor",
            "vendor_sku": "PV-24",
            "notes": "",
            "active": True,
        }
        return base | changes

    def equipment_body(self, **changes):
        base = {
            "location_id": "l1",
            "name": "Wide Format Printer",
            "category": "Printer",
            "asset_tag": "WF-1",
            "manufacturer": "Example",
            "model": "Pro 9000",
            "serial_number": "SN123",
            "status": "Operational",
            "purchase_date": None,
            "warranty_expiration": None,
            "vendor": "Equipment Vendor",
            "service_provider": "Service Co",
            "next_service_date": (datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1)).isoformat(),
            "notes": "",
            "active": True,
        }
        return base | changes

    def test_inventory_adjustment_history_summary_and_conflict(self):
        created = self.client.post(
            "/api/inventory",
            json=self.inventory_body(),
            headers=self.headers,
        )
        self.assertEqual(created.status_code, 201, created.text)
        item = created.json()
        self.assertEqual(item["quantity"], 10)
        self.assertFalse(item["low_stock"])

        self.login("e", "employee", "l1")
        adjusted = self.client.post(
            f"/api/inventory/{item['id']}/adjust",
            json={
                "version": item["version"],
                "mode": "remove",
                "quantity": 8,
                "reason": "Used",
                "notes": "Production use",
            },
            headers=self.headers,
        )
        self.assertEqual(adjusted.status_code, 200, adjusted.text)
        adjusted_item = adjusted.json()
        self.assertEqual(adjusted_item["quantity"], 2)
        self.assertTrue(adjusted_item["low_stock"])

        stale = self.client.post(
            f"/api/inventory/{item['id']}/adjust",
            json={
                "version": item["version"],
                "mode": "remove",
                "quantity": 1,
                "reason": "Used",
                "notes": "",
            },
            headers=self.headers,
        )
        self.assertEqual(stale.status_code, 409)

        too_low = self.client.post(
            f"/api/inventory/{item['id']}/adjust",
            json={
                "version": adjusted_item["version"],
                "mode": "remove",
                "quantity": 50,
                "reason": "Used",
                "notes": "",
            },
            headers=self.headers,
        )
        self.assertEqual(too_low.status_code, 400)

        history = self.client.get(f"/api/inventory/{item['id']}/history")
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()["adjustments"]), 2)
        self.assertEqual(history.json()["adjustments"][0]["adjusted_by_name"], "Employee")

        summary = self.client.get("/api/inventory/summary").json()
        self.assertEqual(summary["active_items"], 1)
        self.assertEqual(summary["low_stock"], 1)
        self.assertEqual(summary["out_of_stock"], 0)

    def test_inventory_management_permissions(self):
        self.login("e", "employee", "l1")
        denied = self.client.post(
            "/api/inventory",
            json=self.inventory_body(),
            headers=self.headers,
        )
        self.assertEqual(denied.status_code, 403)

        self.login("s", "supervisor", "l1")
        wrong_store = self.client.post(
            "/api/inventory",
            json=self.inventory_body(location_id="l2"),
            headers=self.headers,
        )
        self.assertEqual(wrong_store.status_code, 403)

        self.login("a", "admin", "l1")
        allowed = self.client.post(
            "/api/inventory",
            json=self.inventory_body(location_id="l2", name="Selden toner"),
            headers=self.headers,
        )
        self.assertEqual(allowed.status_code, 201, allowed.text)

    def test_equipment_issue_service_history_and_summary(self):
        created = self.client.post(
            "/api/equipment",
            json=self.equipment_body(),
            headers=self.headers,
        )
        self.assertEqual(created.status_code, 201, created.text)
        equipment = created.json()
        self.assertTrue(equipment["service_overdue"])

        self.login("e", "employee", "l1")
        reported = self.client.post(
            f"/api/equipment/{equipment['id']}/report-issue",
            json={"version": equipment["version"], "summary": "Paper feed error"},
            headers=self.headers,
        )
        self.assertEqual(reported.status_code, 200, reported.text)
        issue_asset = reported.json()
        self.assertEqual(issue_asset["status"], "Needs Attention")

        summary = self.client.get("/api/equipment/summary").json()
        self.assertEqual(summary["needs_attention"], 1)
        self.assertEqual(summary["service_overdue"], 1)

        denied_service = self.client.post(
            f"/api/equipment/{equipment['id']}/service-events",
            json={
                "version": issue_asset["version"],
                "event_date": datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
                "event_type": "Repair",
                "summary": "Cleared feed path",
                "provider": "Service Co",
                "cost": 125,
                "status_after": "Operational",
                "next_service_date": (datetime.now(ZoneInfo("America/New_York")).date() + timedelta(days=90)).isoformat(),
            },
            headers=self.headers,
        )
        self.assertEqual(denied_service.status_code, 403)

        self.login("s", "supervisor", "l1")
        serviced = self.client.post(
            f"/api/equipment/{equipment['id']}/service-events",
            json={
                "version": issue_asset["version"],
                "event_date": datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
                "event_type": "Repair",
                "summary": "Cleared feed path",
                "provider": "Service Co",
                "cost": 125,
                "status_after": "Operational",
                "next_service_date": (datetime.now(ZoneInfo("America/New_York")).date() + timedelta(days=90)).isoformat(),
            },
            headers=self.headers,
        )
        self.assertEqual(serviced.status_code, 201, serviced.text)
        serviced_asset = serviced.json()["equipment"]
        self.assertEqual(serviced_asset["status"], "Operational")
        self.assertFalse(serviced_asset["service_overdue"])

        history = self.client.get(f"/api/equipment/{equipment['id']}/history")
        self.assertEqual(history.status_code, 200, history.text)
        events = history.json()["events"]
        self.assertEqual(len(events), 2)
        self.assertEqual({event["event_type"] for event in events}, {"Issue Reported", "Repair"})

    def test_equipment_store_scope_and_admin_cross_store(self):
        self.login("s", "supervisor", "l1")
        wrong_store = self.client.post(
            "/api/equipment",
            json=self.equipment_body(location_id="l2", name="Selden Cutter"),
            headers=self.headers,
        )
        self.assertEqual(wrong_store.status_code, 403)

        self.login("a", "admin", "l1")
        allowed = self.client.post(
            "/api/equipment",
            json=self.equipment_body(location_id="l2", name="Selden Cutter"),
            headers=self.headers,
        )
        self.assertEqual(allowed.status_code, 201, allowed.text)


if __name__ == "__main__":
    unittest.main()
