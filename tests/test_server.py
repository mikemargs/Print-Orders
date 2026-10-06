import atexit
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory()
atexit.register(TEMP.cleanup)
os.environ["DATABASE_URL"] = f"sqlite:///{Path(TEMP.name) / 'server.db'}"
os.environ["JWT_SECRET"] = "test-secret-that-is-longer-than-thirty-two-characters"
os.environ["BOOTSTRAP_COMPANY_NAME"] = "Test Print Company"
os.environ["BOOTSTRAP_COMPANY_CODE"] = "TEST-PRINT"
os.environ["BOOTSTRAP_COMPANY_PASSWORD"] = "company-password"
os.environ["BOOTSTRAP_ADMIN_NAME"] = "Test Admin"
os.environ["BOOTSTRAP_ADMIN_PIN"] = "246810"
os.environ["WEB_COOKIE_SECURE"] = "0"
sys.path.insert(0, str(ROOT / "server"))

import app.main as main_module
from app.database import Base, Company, Customer, Employee, Location, SessionLocal, engine
from app.main import app
from app.security import hash_secret, make_token
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

    def snapshot(self):
        return self.client.get(
            "/api/sync/snapshot",
            headers={"Authorization": f"Bearer {self.employee_token}"},
        ).json()


class ServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)
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
        engine.dispose()

    def test_api_responses_include_baseline_browser_security_headers(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(response.headers.get("x-frame-options"), "DENY")
        self.assertEqual(response.headers.get("referrer-policy"), "no-referrer")
        self.assertEqual(
            response.headers.get("permissions-policy"),
            "camera=(), microphone=(), geolocation=()",
        )

    def test_production_responses_include_hsts(self):
        old = os.environ.get("APP_ENV")
        os.environ["APP_ENV"] = "production"
        try:
            response = self.client.get("/api/health")
            self.assertEqual(
                response.headers.get("strict-transport-security"),
                "max-age=31536000; includeSubDomains",
            )
        finally:
            if old is None:
                os.environ.pop("APP_ENV", None)
            else:
                os.environ["APP_ENV"] = old

    def test_last_active_admin_cannot_be_disabled_or_demoted(self):
        disabled = self.client.patch(
            f"/api/admin/employees/{self.admin['id']}",
            headers=self.headers,
            json={"active": False},
        )
        self.assertEqual(disabled.status_code, 400, disabled.text)

        demoted = self.client.patch(
            f"/api/admin/employees/{self.admin['id']}",
            headers=self.headers,
            json={"role": "employee"},
        )
        self.assertEqual(demoted.status_code, 400, demoted.text)

    def test_last_admin_guard_uses_postgresql_row_lock(self):
        from app.main import active_admin_lock_query
        from sqlalchemy.dialects import postgresql

        statement = active_admin_lock_query("company-1")
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("FOR UPDATE", sql)

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
        self.assertAlmostEqual(result["server"]["total"], 108.63)
        self.assertAlmostEqual(result["server"]["balance"], 83.63)

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


    def test_operation_ids_are_company_scoped(self):
        other_company_id = str(uuid.uuid4())
        other_location_id = str(uuid.uuid4())
        other_employee_id = str(uuid.uuid4())
        with SessionLocal() as db:
            db.add(Company(id=other_company_id, name="Other Company", code=f"OTHER-{uuid.uuid4().hex[:8]}", password_hash=hash_secret("pw"), active=True))
            db.add(Location(id=other_location_id, company_id=other_company_id, name="Other", store_number="9999", active=True))
            db.add(Employee(id=other_employee_id, company_id=other_company_id, name="Other Admin", pin_hash=hash_secret("1234"), role="admin", location_ids=[other_location_id], active=True))
            db.commit()

        shared_op_id = str(uuid.uuid4())
        first_entity = str(uuid.uuid4())
        first = self.client.post(
            "/api/sync/push", headers=self.headers,
            json={"operations": [{"operation_id": shared_op_id, "entity_type": "customer", "action": "upsert", "entity_id": first_entity, "base_version": 0, "payload": {"company": "First tenant"}}]},
        )
        self.assertEqual(first.status_code, 200, first.text)
        second_entity = str(uuid.uuid4())
        other_token = make_token(other_company_id, "employee", other_employee_id, "admin", location_id=other_location_id, auth_version=1)
        second = self.client.post(
            "/api/sync/push", headers={"Authorization": f"Bearer {other_token}"},
            json={"operations": [{"operation_id": shared_op_id, "entity_type": "customer", "action": "upsert", "entity_id": second_entity, "base_version": 0, "payload": {"company": "Second tenant"}}]},
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["results"][0]["entity_id"], second_entity)
        self.assertNotEqual(second.json()["results"][0]["entity_id"], first_entity)

    def test_existing_order_rejects_foreign_relationships(self):
        customer_id = str(uuid.uuid4())
        order_id = str(uuid.uuid4())
        create_customer = {"operation_id": str(uuid.uuid4()), "entity_type": "customer", "action": "upsert", "entity_id": customer_id, "base_version": 0, "payload": {"company": "Owned"}}
        self.client.post("/api/sync/push", headers=self.headers, json={"operations": [create_customer]})
        create_order = {"operation_id": str(uuid.uuid4()), "entity_type": "order", "action": "upsert", "entity_id": order_id, "base_version": 0, "payload": {"customer_id": customer_id, "location_id": self.location["id"], "order_number": "OWNED-1", "status": "New", "priority": "Normal", "received_date": "2026-10-03", "items": [{"item_name": "Poster", "quantity": 1, "unit_price": 10}]}}
        made = self.client.post("/api/sync/push", headers=self.headers, json={"operations": [create_order]}).json()["results"][0]
        self.assertEqual(made["status"], "applied")

        other_company_id = str(uuid.uuid4()); foreign_customer_id = str(uuid.uuid4()); foreign_location_id = str(uuid.uuid4())
        with SessionLocal() as db:
            db.add(Company(id=other_company_id, name="Foreign", code=f"FOREIGN-{uuid.uuid4().hex[:8]}", password_hash=hash_secret("pw"), active=True))
            db.add(Customer(id=foreign_customer_id, company_id=other_company_id, company="Foreign Customer"))
            db.add(Location(id=foreign_location_id, company_id=other_company_id, name="Foreign Store", store_number="8888", active=True))
            db.commit()
        edit = {"operation_id": str(uuid.uuid4()), "entity_type": "order", "action": "upsert", "entity_id": order_id, "base_version": 1, "payload": {"customer_id": foreign_customer_id, "location_id": foreign_location_id, "description": "should reject"}}
        result = self.client.post("/api/sync/push", headers=self.headers, json={"operations": [edit]}).json()["results"][0]
        self.assertIn(result["status"], {"invalid", "forbidden"})

    def test_employee_cannot_mutate_unassigned_store(self):
        bootstrap = self.client.get("/api/bootstrap", headers={"Authorization": f"Bearer {self.company_token}"}).json()
        other_location = next(x for x in bootstrap["locations"] if x["id"] != self.location["id"])
        employee_id = str(uuid.uuid4())
        with SessionLocal() as db:
            db.add(Employee(id=employee_id, company_id=self.admin["id"] if False else self.client.post("/api/auth/company-login", json={"company_code": "TEST-PRINT", "password": "company-password"}).json()["company"]["id"], name="Store Employee", pin_hash=hash_secret("1234"), role="employee", location_ids=[self.location["id"]], active=True))
            db.commit()
        login = self.client.post("/api/auth/employee-login", headers={"Authorization": f"Bearer {self.company_token}"}, json={"employee_id": employee_id, "pin": "1234", "location_id": self.location["id"]})
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["token"]
        customer_id = str(uuid.uuid4())
        self.client.post("/api/sync/push", headers=self.headers, json={"operations": [{"operation_id": str(uuid.uuid4()), "entity_type": "customer", "action": "upsert", "entity_id": customer_id, "base_version": 0, "payload": {"company": "Store Customer"}}]})
        order_id = str(uuid.uuid4())
        made = self.client.post("/api/sync/push", headers=self.headers, json={"operations": [{"operation_id": str(uuid.uuid4()), "entity_type": "order", "action": "upsert", "entity_id": order_id, "base_version": 0, "payload": {"customer_id": customer_id, "location_id": other_location["id"], "order_number": "OTHERSTORE", "status": "New", "priority": "Normal", "received_date": "2026-10-03", "items": [{"item_name": "Sign", "quantity": 1, "unit_price": 5}]}}]}).json()["results"][0]
        self.assertEqual(made["status"], "applied")
        denied = self.client.post("/api/sync/push", headers={"Authorization": f"Bearer {token}"}, json={"operations": [{"operation_id": str(uuid.uuid4()), "entity_type": "order", "action": "upsert", "entity_id": order_id, "base_version": 1, "payload": {"description": "nope"}}]}).json()["results"][0]
        self.assertEqual(denied["status"], "forbidden")

    def test_legacy_employee_token_requires_reauthentication(self):
        legacy = make_token(self.client.post("/api/auth/company-login", json={"company_code": "TEST-PRINT", "password": "company-password"}).json()["company"]["id"], "employee", self.admin["id"], "admin")
        response = self.client.post("/api/sync/push", headers={"Authorization": f"Bearer {legacy}"}, json={"operations": []})
        self.assertIn(response.status_code, {401, 403})

    def test_employee_auth_version_changes_and_inactive_employee_bootstraps(self):
        created = self.client.post("/api/admin/employees", headers=self.headers, json={"name": "Revocable", "pin": "1111", "role": "employee", "location_ids": [self.location["id"]]})
        self.assertEqual(created.status_code, 200, created.text)
        employee = created.json()["employee"]
        self.assertEqual(employee["auth_version"], 1)
        changed = self.client.patch(f"/api/admin/employees/{employee['id']}", headers=self.headers, json={"pin": "2222"})
        self.assertEqual(changed.json()["employee"]["auth_version"], 2)
        disabled = self.client.patch(f"/api/admin/employees/{employee['id']}", headers=self.headers, json={"active": False})
        self.assertEqual(disabled.json()["employee"]["auth_version"], 3)
        bootstrap = self.client.get("/api/bootstrap", headers={"Authorization": f"Bearer {self.company_token}"}).json()
        cached = next(x for x in bootstrap["employees"] if x["id"] == employee["id"] )
        self.assertFalse(cached["active"]); self.assertEqual(cached["auth_version"], 3)

    def test_order_payload_validation_and_half_up_rounding(self):
        customer_id = str(uuid.uuid4())
        self.client.post("/api/sync/push", headers=self.headers, json={"operations": [{"operation_id": str(uuid.uuid4()), "entity_type": "customer", "action": "upsert", "entity_id": customer_id, "base_version": 0, "payload": {"company": "Validation Customer"}}]})
        invalid = self.client.post("/api/sync/push", headers=self.headers, json={"operations": [{"operation_id": str(uuid.uuid4()), "entity_type": "order", "action": "upsert", "entity_id": str(uuid.uuid4()), "base_version": 0, "payload": {"customer_id": customer_id, "location_id": self.location["id"], "order_number": "BAD", "status": "Bananas", "priority": "Normal", "received_date": "not-a-date", "items": [{"item_name": "Bad", "quantity": -1, "unit_price": -2}]}}]}).json()["results"][0]
        self.assertEqual(invalid["status"], "invalid")

        rounded = self.client.post("/api/sync/push", headers=self.headers, json={"operations": [{"operation_id": str(uuid.uuid4()), "entity_type": "order", "action": "upsert", "entity_id": str(uuid.uuid4()), "base_version": 0, "payload": {"customer_id": customer_id, "location_id": self.location["id"], "order_number": "ROUND", "status": "New", "priority": "Normal", "received_date": "2026-10-03", "tax_rate": 8.625, "items": [{"item_name": "One", "quantity": 1, "unit_price": 100}]}}]}).json()["results"][0]
        self.assertEqual(rounded["status"], "applied")
        self.assertEqual(rounded["server"]["total"], 108.63)

    def test_last_active_admin_cannot_be_disabled(self):
        response = self.client.patch(f"/api/admin/employees/{self.admin['id']}", headers=self.headers, json={"active": False})
        self.assertEqual(response.status_code, 400, response.text)

    def test_company_login_is_throttled_after_repeated_failures(self):
        import os

        from app.security import reset_login_throttle
        reset_login_throttle()
        old = os.environ.get("LOGIN_MAX_ATTEMPTS")
        os.environ["LOGIN_MAX_ATTEMPTS"] = "2"
        try:
            for _ in range(2):
                r = self.client.post("/api/auth/company-login", json={"company_code": "TEST-PRINT", "password": "wrong"})
                self.assertEqual(r.status_code, 401)
            blocked = self.client.post("/api/auth/company-login", json={"company_code": "TEST-PRINT", "password": "wrong"})
            self.assertEqual(blocked.status_code, 429)
        finally:
            reset_login_throttle()
            if old is None: os.environ.pop("LOGIN_MAX_ATTEMPTS", None)
            else: os.environ["LOGIN_MAX_ATTEMPTS"] = old

    def test_health_reports_database_failure(self):
        original = main_module.database_probe if hasattr(main_module, "database_probe") else None
        def fail(_db):
            raise RuntimeError("db down")
        main_module.database_probe = fail
        try:
            response = self.client.get("/api/health")
            self.assertEqual(response.status_code, 503)
        finally:
            if original is None: delattr(main_module, "database_probe")
            else: main_module.database_probe = original

    def test_sync_snapshot_returns_current_state_and_cursor(self):
        customer_id = str(uuid.uuid4())
        self.client.post("/api/sync/push", headers=self.headers, json={"operations": [{"operation_id": str(uuid.uuid4()), "entity_type": "customer", "action": "upsert", "entity_id": customer_id, "base_version": 0, "payload": {"company": "Snapshot Customer"}}]})
        response = self.client.get("/api/sync/snapshot", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(any(x["id"] == customer_id for x in body["customers"]))
        self.assertGreaterEqual(body["cursor"], 1)

    def test_employee_session_rejects_inactive_company(self):
        company_id = str(uuid.uuid4()); location_id = str(uuid.uuid4()); employee_id = str(uuid.uuid4())
        with SessionLocal() as db:
            db.add(Company(id=company_id, name="Disabled Later", code=f"DIS-{uuid.uuid4().hex[:8]}", password_hash=hash_secret("pw"), active=True))
            db.add(Location(id=location_id, company_id=company_id, name="Store", store_number="7777", active=True))
            db.add(Employee(id=employee_id, company_id=company_id, name="Admin", pin_hash=hash_secret("1234"), role="admin", location_ids=[location_id], active=True, auth_version=1))
            db.commit()
        token = make_token(company_id, "employee", employee_id, "admin", location_id=location_id, auth_version=1)
        with SessionLocal() as db:
            db.get(Company, company_id).active = False
            db.commit()
        response = self.client.get("/api/sync/pull", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(response.status_code, 403)

    def test_web_session_uses_httponly_cookie_and_csrf(self):
        client = TestClient(app, base_url="https://testserver")
        with client:
            company = client.post("/api/web/auth/company", json={"company_code": "TEST-PRINT", "password": "company-password"})
            self.assertEqual(company.status_code, 200, company.text)
            self.assertIn("httponly", company.headers.get("set-cookie", "").lower())
            employee = client.post("/api/web/auth/employee", json={"employee_id": self.admin["id"], "pin": "246810", "location_id": self.location["id"]})
            self.assertEqual(employee.status_code, 200, employee.text)
            csrf = employee.json()["csrf_token"]
            session = client.get("/api/web/session")
            self.assertEqual(session.status_code, 200, session.text)
            self.assertTrue(any(x["id"] == self.location["id"] for x in session.json()["locations"]))
            denied = client.post("/api/web/auth/logout")
            self.assertEqual(denied.status_code, 403)
            allowed = client.post("/api/web/auth/logout", headers={"X-CSRF-Token": csrf})
            self.assertEqual(allowed.status_code, 200, allowed.text)

    def test_web_session_revokes_after_employee_auth_change(self):
        created = self.client.post("/api/admin/employees", headers=self.headers, json={"name":"Web User","pin":"4444","role":"employee","location_ids":[self.location["id"]]}).json()["employee"]
        client = TestClient(app, base_url="https://testserver")
        with client:
            client.post("/api/web/auth/company", json={"company_code":"TEST-PRINT","password":"company-password"})
            login = client.post("/api/web/auth/employee", json={"employee_id":created["id"],"pin":"4444","location_id":self.location["id"]})
            self.assertEqual(login.status_code,200,login.text)
            changed = self.client.patch(f"/api/admin/employees/{created['id']}", headers=self.headers, json={"pin":"5555"})
            self.assertEqual(changed.status_code,200,changed.text)
            self.assertEqual(client.get("/api/web/session").status_code,401)

    def _login_web_admin(self):
        client = TestClient(app, base_url="https://testserver")
        client.__enter__()
        company = client.post("/api/web/auth/company", json={"company_code":"TEST-PRINT","password":"company-password"})
        self.assertEqual(company.status_code,200,company.text)
        employee = client.post("/api/web/auth/employee", json={"employee_id":self.admin["id"],"pin":"246810","location_id":self.location["id"]})
        self.assertEqual(employee.status_code,200,employee.text)
        return client, employee.json()["csrf_token"]

    def test_web_customer_crud_version_conflict_and_sync_event(self):
        client, csrf = self._login_web_admin()
        try:
            before = self.client.get("/api/sync/pull?cursor=0", headers=self.headers).json()["cursor"]
            denied = client.post("/api/customers", json={"company":"Web Customer"})
            self.assertEqual(denied.status_code,403)
            created = client.post("/api/customers", headers={"X-CSRF-Token":csrf}, json={"company":"Web Customer","first_name":"Alex"})
            self.assertEqual(created.status_code,201,created.text)
            customer = created.json(); self.assertEqual(customer["version"],1)
            listed = client.get("/api/customers?search=Web%20Customer").json()["customers"]
            self.assertTrue(any(x["id"] == customer["id"] for x in listed))
            updated = client.patch(f"/api/customers/{customer['id']}", headers={"X-CSRF-Token":csrf}, json={"version":1,"company":"Web Customer Updated"})
            self.assertEqual(updated.status_code,200,updated.text); self.assertEqual(updated.json()["version"],2)
            stale = client.patch(f"/api/customers/{customer['id']}", headers={"X-CSRF-Token":csrf}, json={"version":1,"company":"Stale"})
            self.assertEqual(stale.status_code,409,stale.text); self.assertIn("current", stale.json())
            events = self.client.get(f"/api/sync/pull?cursor={before}", headers=self.headers).json()["events"]
            self.assertTrue(any(x["entity_id"] == customer["id"] for x in events))
        finally:
            client.__exit__(None,None,None)

    def test_web_order_crud_filters_and_authoritative_totals(self):
        client, csrf = self._login_web_admin()
        try:
            customer = client.post("/api/customers", headers={"X-CSRF-Token":csrf}, json={"company":"Order Web Customer"}).json()
            order = client.post("/api/orders", headers={"X-CSRF-Token":csrf}, json={"customer_id":customer["id"],"location_id":self.location["id"],"status":"New","priority":"Rush","received_date":"2026-10-03","due_date":"2026-10-08","tax_rate":8.625,"items":[{"item_name":"Poster","quantity":1,"unit_price":100}]})
            self.assertEqual(order.status_code,201,order.text)
            body=order.json(); self.assertEqual(body["total"],108.63); self.assertTrue(body["order_number"])
            listed=client.get(f"/api/orders?location_id={self.location['id']}&priority=Rush&due_start=2026-10-07&due_end=2026-10-09").json()["orders"]
            self.assertTrue(any(x["id"]==body["id"] for x in listed))
            outside=client.get("/api/orders?due_end=2026-10-07").json()["orders"]
            self.assertFalse(any(x["id"]==body["id"] for x in outside))
            updated=client.patch(f"/api/orders/{body['id']}", headers={"X-CSRF-Token":csrf}, json={"version":1,"description":"Updated from web"})
            self.assertEqual(updated.status_code,200,updated.text); self.assertEqual(updated.json()["version"],2)
        finally:
            client.__exit__(None,None,None)

    def test_web_new_order_queues_internal_store_notification(self):
        client, csrf = self._login_web_admin()
        try:
            customer = client.post(
                "/api/customers",
                headers={"X-CSRF-Token": csrf},
                json={"company": "Notification Customer"},
            ).json()
            with patch("app.routers.orders.queue_work_order_created") as notify:
                response = client.post(
                    "/api/orders",
                    headers={"X-CSRF-Token": csrf},
                    json={
                        "customer_id": customer["id"],
                        "location_id": self.location["id"],
                        "status": "New",
                        "priority": "Normal",
                        "received_date": "2026-10-06",
                        "description": "Notification test",
                        "items": [{"item_name": "Poster", "quantity": 1, "unit_price": 10}],
                    },
                )
            self.assertEqual(response.status_code, 201, response.text)
            notify.assert_called_once()
            self.assertEqual(notify.call_args.args[2].id, response.json()["id"])
        finally:
            client.__exit__(None, None, None)

    def test_synced_new_order_queues_notification_once_on_replay(self):
        client, csrf = self._login_web_admin()
        try:
            customer = client.post(
                "/api/customers",
                headers={"X-CSRF-Token": csrf},
                json={"company": "Synced Notification Customer"},
            ).json()
        finally:
            client.__exit__(None, None, None)
        operation_id = str(uuid.uuid4())
        order_id = str(uuid.uuid4())
        body = {
            "operations": [
                {
                    "operation_id": operation_id,
                    "entity_type": "order",
                    "action": "upsert",
                    "entity_id": order_id,
                    "base_version": 0,
                    "payload": {
                        "customer_id": customer["id"],
                        "location_id": self.location["id"],
                        "status": "New",
                        "priority": "Normal",
                        "received_date": "2026-10-06",
                        "description": "Synced notification test",
                    },
                }
            ]
        }
        with patch("app.main.queue_work_order_created") as notify:
            first = self.client.post("/api/sync/push", headers=self.headers, json=body)
            second = self.client.post("/api/sync/push", headers=self.headers, json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["results"][0]["status"], "applied")
        self.assertEqual(second.status_code, 200, second.text)
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[2].id, order_id)

    def test_web_reports_and_employee_admin_require_csrf_for_writes(self):
        client, csrf = self._login_web_admin()
        try:
            report = client.get("/api/reports/summary")
            self.assertEqual(report.status_code, 200, report.text)
            employees = client.get("/api/admin/employees")
            self.assertEqual(employees.status_code, 200, employees.text)
            denied = client.post("/api/admin/employees", json={"name":"Cookie Employee","pin":"6666","role":"employee","location_ids":[self.location["id"]]})
            self.assertEqual(denied.status_code, 403)
            created = client.post("/api/admin/employees", headers={"X-CSRF-Token":csrf}, json={"name":"Cookie Employee","pin":"6666","role":"employee","location_ids":[self.location["id"]]})
            self.assertEqual(created.status_code, 200, created.text)
        finally:
            client.__exit__(None,None,None)

    def test_web_artwork_upload_finalize_download_and_delete(self):
        from app.storage import set_storage
        from app.storage.fake import FakeStorageAdapter
        storage = FakeStorageAdapter(); set_storage(storage)
        client, csrf = self._login_web_admin()
        try:
            customer = client.post("/api/customers", headers={"X-CSRF-Token":csrf}, json={"company":"Artwork Customer"}).json()
            order = client.post("/api/orders", headers={"X-CSRF-Token":csrf}, json={"customer_id":customer["id"],"location_id":self.location["id"],"status":"New","priority":"Normal","received_date":"2026-10-03","items":[{"item_name":"Banner","quantity":1,"unit_price":10}]}).json()
            other_order = client.post("/api/orders", headers={"X-CSRF-Token":csrf}, json={"customer_id":customer["id"],"location_id":self.location["id"],"status":"New","priority":"Normal","received_date":"2026-10-03","items":[{"item_name":"Poster","quantity":1,"unit_price":8}]}).json()

            def artwork_status(order_id):
                rows = client.get(f"/api/orders?location_id={self.location['id']}&limit=250").json()["orders"]
                return next(x["has_artwork"] for x in rows if x["id"] == order_id)

            self.assertFalse(artwork_status(order["id"]))
            self.assertFalse(artwork_status(other_order["id"]))

            too_big = client.post(f"/api/orders/{order['id']}/files/upload-authorizations", headers={"X-CSRF-Token":csrf}, json={"filename":"huge.pdf","mime_type":"application/pdf","size_bytes":400*1024*1024})
            self.assertEqual(too_big.status_code,400)
            disguised_executable = client.post(f"/api/orders/{order['id']}/files/upload-authorizations", headers={"X-CSRF-Token":csrf}, json={"filename":"invoice.exe","mime_type":"application/octet-stream","size_bytes":10})
            self.assertEqual(disguised_executable.status_code,400)
            auth = client.post(f"/api/orders/{order['id']}/files/upload-authorizations", headers={"X-CSRF-Token":csrf}, json={"filename":"../../evil name.pdf","mime_type":"application/pdf","size_bytes":10})
            self.assertEqual(auth.status_code,201,auth.text)
            payload=auth.json(); self.assertNotIn("..",payload["object_key"]); self.assertTrue(payload["object_key"].endswith("evil_name.pdf")); self.assertEqual(payload["chunk_size"],6*1024*1024)
            attachment_id=payload["attachment"]["id"]
            storage.mark_uploaded(payload["object_key"], b"0123456789", "application/pdf")
            finalized=client.post(f"/api/orders/{order['id']}/files/finalize", headers={"X-CSRF-Token":csrf}, json={"attachment_id":attachment_id})
            self.assertEqual(finalized.status_code,200,finalized.text); self.assertTrue(finalized.json()["active"])
            self.assertTrue(artwork_status(order["id"]))
            self.assertFalse(artwork_status(other_order["id"]))

            listed=client.get(f"/api/orders/{order['id']}/files").json()["files"]
            self.assertTrue(any(x["id"]==attachment_id for x in listed))
            download=client.get(f"/api/orders/{order['id']}/files/{attachment_id}/download")
            self.assertEqual(download.status_code,200,download.text); self.assertTrue(download.json()["url"].startswith("https://fake-storage/"))
            deleted=client.delete(f"/api/orders/{order['id']}/files/{attachment_id}", headers={"X-CSRF-Token":csrf})
            self.assertEqual(deleted.status_code,200,deleted.text)
            self.assertFalse(any(x["id"]==attachment_id for x in client.get(f"/api/orders/{order['id']}/files").json()["files"]))
            self.assertFalse(artwork_status(order["id"]))
        finally:
            client.__exit__(None,None,None)

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
            self.assertGreaterEqual(result["pulled"], 0)
            self.assertEqual(second.get_customer(customer_id)["company"], "Desktop Round Trip")
            self.assertEqual(second.get_order(order_id)["description"], "Round-trip order")


if __name__ == "__main__":
    unittest.main()
