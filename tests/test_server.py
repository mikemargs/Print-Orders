import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEMP.name) / 'server.db'}"
os.environ["JWT_SECRET"] = "test-secret-that-is-longer-than-thirty-two-characters"
os.environ["BOOTSTRAP_COMPANY_NAME"] = "Test Print Company"
os.environ["BOOTSTRAP_COMPANY_CODE"] = "TEST-PRINT"
os.environ["BOOTSTRAP_COMPANY_PASSWORD"] = "company-password"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Test Admin"
os.environ["BOOTSTRAP_ADMIN_PIN"] = "246810"
sys.path.insert(0, str(ROOT / "server"))

from app.main import app
from fastapi.testclient import TestClient

sys.path.insert(0, str(ROOT / "client"))
from local_store import LocalStore
from sync_engine import sync_once


class InProcessApi:
    """Small adapter that lets the real desktop sync engine use TestClient."""

    def __init__(self, client, company_token, employee_token):
        self.client = client
        self.company_token = company_token
        self.employee_token = employee_token

    def bootstrap(self):
        return self.client.get(
            "/api/bootstrap",
            headers={"Authorization": f"Bearer {self.company_token}"},
        ).json()

    def push(self, operations):
        return self.client.post(
            "/api/sync/push",
            headers={"Authorization": f"Bearer {self.employee_token}"},
            json={"operations": operations},
        ).json()

    def pull(self, cursor, limit=500):
        return self.client.get(
            "/api/sync/pull",
            headers={"Authorization": f"Bearer {self.employee_token}"},
            params={"cursor": cursor, "limit": limit},
        ).json()


class ServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()
        login = cls.client.post(
            "/api/auth/company-login",
            json={
                "company_code": "TEST-PRINT",
                "password": "company-password",
            },
        )
        assert login.status_code == 200, login.text
        cls.company_token = login.json()["token"]
        bootstrap = cls.client.get(
            "/api/bootstrap", headers={"Authorization": f"Bearer {cls.company_token}"}
        ).json()
        cls.location = bootstrap["locations"][0]
        cls.admin = bootstrap["employees"][0]
        employee_login = cls.client.post(
            "/api/auth/employee-login",
            headers={"Authorization": f"Bearer {cls.company_token}"},
            json={
                "employee_id": cls.admin["id"],
                "pin": "246810",
                "location_id": cls.location["id"],
            },
        )
        assert employee_login.status_code == 200, employee_login.text
        cls.employee_token = employee_login.json()["token"]
        cls.headers = {"Authorization": f"Bearer {cls.employee_token}"}

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        TEMP.cleanup()

    def test_authentication_rejects_bad_password(self):
        response = self.client.post(
            "/api/auth/company-login",
            json={
                "company_code": "TEST-PRINT",
                "password": "wrong",
            },
        )
        self.assertEqual(response.status_code, 401)

    def test_sync_pull_conflict_and_report(self):
        customer_id = str(uuid.uuid4())
        customer_op = {
            "operation_id": str(uuid.uuid4()),
            "entity_type": "customer",
            "action": "upsert",
            "entity_id": customer_id,
            "base_version": 0,
            "payload": {
                "company": "Integration Customer",
                "first_name": "Sam",
                "last_name": "Jones",
            },
        }
        response = self.client.post(
            "/api/sync/push", headers=self.headers, json={"operations": [customer_op]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["status"], "applied")
        self.assertEqual(response.json()["results"][0]["version"], 1)

        order_id = str(uuid.uuid4())
        order_op = {
            "operation_id": str(uuid.uuid4()),
            "entity_type": "order",
            "action": "upsert",
            "entity_id": order_id,
            "base_version": 0,
            "payload": {
                "customer_id": customer_id,
                "location_id": self.location["id"],
                "order_number": "WO-5127-TEST1",
                "status": "New",
                "priority": "Normal",
                "received_date": "2026-09-16",
                "due_date": "2026-09-20",
                "tax_rate": 8.625,
                "discount": 0,
                "deposit": 25,
                "items": [{"item_name": "Poster", "quantity": 2, "unit_price": 50}],
            },
        }
        response = self.client.post(
            "/api/sync/push", headers=self.headers, json={"operations": [order_op]}
        )
        result = response.json()["results"][0]
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["server"]["subtotal"], 100)
        self.assertAlmostEqual(result["server"]["total"], 108.62)
        self.assertAlmostEqual(result["server"]["balance"], 83.62)

        duplicate_edit = dict(customer_op)
        duplicate_edit["operation_id"] = str(uuid.uuid4())
        duplicate_edit["payload"] = {"company": "Stale Edit"}
        conflict = self.client.post(
            "/api/sync/push",
            headers=self.headers,
            json={"operations": [duplicate_edit]},
        ).json()["results"][0]
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(conflict["server"]["company"], "Integration Customer")

        pulled = self.client.get("/api/sync/pull?cursor=0", headers=self.headers).json()
        self.assertGreaterEqual(len(pulled["events"]), 2)
        report = self.client.get("/api/reports/summary", headers=self.headers).json()
        self.assertGreaterEqual(report["total_orders"], 1)
        self.assertGreaterEqual(report["total_sales"], 108.62)

    def test_admin_can_create_employee(self):
        response = self.client.post(
            "/api/admin/employees",
            headers=self.headers,
            json={
                "name": "Test Employee",
                "pin": "123456",
                "role": "employee",
                "location_ids": [self.location["id"]],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["employee"]["name"], "Test Employee")
        self.assertNotIn("pin", response.text)

    def test_real_desktop_sync_engine_round_trip(self):
        api = InProcessApi(self.client, self.company_token, self.employee_token)
        with tempfile.TemporaryDirectory() as folder:
            first = LocalStore(Path(folder) / "first-store.db")
            first.cache_bootstrap(api.bootstrap())
            customer_id = first.save_customer({"company": "Desktop Round Trip"})
            order_id = first.save_order(
                {
                    "customer_id": customer_id,
                    "location_id": self.location["id"],
                    "status": "In Production",
                    "priority": "Rush",
                    "received_date": "2026-09-16",
                    "due_date": "2026-09-17",
                    "tax_rate": 0,
                    "deposit": 0,
                    "discount": 0,
                    "description": "Round-trip order",
                },
                [{"item_name": "Yard Sign", "quantity": 3, "unit_price": 20}],
            )
            result = sync_once(first, api)
            self.assertEqual(result["pending"], 0)

            second = LocalStore(Path(folder) / "second-store.db")
            result = sync_once(second, api)
            self.assertGreaterEqual(result["pulled"], 2)
            self.assertEqual(second.get_customer(customer_id)["company"], "Desktop Round Trip")
            self.assertEqual(second.get_order(order_id)["description"], "Round-trip order")


if __name__ == "__main__":
    unittest.main()
