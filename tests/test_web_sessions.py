import atexit
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_TEMP = tempfile.TemporaryDirectory()
atexit.register(WEB_TEMP.cleanup)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(WEB_TEMP.name) / 'web-session.db'}")
os.environ.setdefault("JWT_SECRET", "web-session-test-secret-longer-than-thirty-two-chars")
sys.path.insert(0, str(ROOT / "server"))

from fastapi.testclient import TestClient
from sqlalchemy import select
from app.database import Base, Company, Employee, Location, SessionLocal, engine
from app.main import app
from app.security import hash_secret


class WebSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_cookie_secure = os.environ.get("WEB_COOKIE_SECURE")
        os.environ["WEB_COOKIE_SECURE"] = "true"
        Base.metadata.create_all(engine)
        with SessionLocal() as db:
            existing = db.scalar(select(Company).where(Company.code == "TEST-PRINT"))
            if existing:
                cls.company_code = "TEST-PRINT"
                cls.company_id = existing.id
                employee = db.scalar(select(Employee).where(Employee.company_id == existing.id, Employee.role == "admin", Employee.active.is_(True)))
                location = db.scalar(select(Location).where(Location.company_id == existing.id, Location.active.is_(True)))
                cls.employee_id = employee.id
                cls.location_id = location.id
            else:
                cls.company_code = f"WEB-{uuid.uuid4().hex[:8]}".upper()
                cls.company_id = str(uuid.uuid4())
                cls.employee_id = str(uuid.uuid4())
                cls.location_id = str(uuid.uuid4())
                db.add(Company(id=cls.company_id, name="Web Test", code=cls.company_code, password_hash=hash_secret("company-password"), active=True))
                db.add(Location(id=cls.location_id, company_id=cls.company_id, name="Web Store", store_number="9000", active=True))
                db.add(Employee(id=cls.employee_id, company_id=cls.company_id, name="Web Admin", pin_hash=hash_secret("246810"), role="admin", location_ids=[cls.location_id], active=True, auth_version=1))
                db.commit()
        cls.ctx = TestClient(app, base_url="https://testserver")
        cls.client = cls.ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.ctx.__exit__(None, None, None)
        engine.dispose()
        if cls.old_cookie_secure is None:
            os.environ.pop("WEB_COOKIE_SECURE", None)
        else:
            os.environ["WEB_COOKIE_SECURE"] = cls.old_cookie_secure

    def login(self):
        company = self.client.post("/api/web/auth/company", json={"company_code":self.company_code,"password":"company-password"})
        self.assertEqual(company.status_code, 200, company.text)
        result = self.client.post("/api/web/auth/employee", json={"employee_id":self.employee_id,"pin":"246810","location_id":self.location_id})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_cookie_session_lifecycle_and_attributes(self):
        response = self.client.post("/api/web/auth/company", json={"company_code":self.company_code,"password":"company-password"})
        cookie = response.headers.get("set-cookie", "").lower()
        self.assertIn("pom_company_challenge", cookie)
        self.assertIn("httponly", cookie)
        self.assertIn("secure", cookie)
        self.assertIn("samesite=strict", cookie)
        employee_response = self.client.post("/api/web/auth/employee", json={"employee_id":self.employee_id,"pin":"246810","location_id":self.location_id})
        self.assertNotIn("token", employee_response.json())
        self.assertTrue(employee_response.json()["csrf_token"])
        self.assertEqual(self.client.get("/api/web/session").status_code, 200)

    def test_logout_requires_csrf_and_clears_session(self):
        body = self.login()
        denied = self.client.post("/api/web/auth/logout")
        self.assertEqual(denied.status_code, 403)
        ok = self.client.post("/api/web/auth/logout", headers={"X-CSRF-Token": body["csrf_token"]})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.get("/api/web/session").status_code, 401)


if __name__ == "__main__":
    unittest.main()
