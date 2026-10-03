import os
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-longer-than-thirty-two-characters")
sys.path.insert(0, str(ROOT / "server"))

from app.auth_context import resolve_employee_context
from app.database import Base, Company, Employee, Location
from app.security import hash_secret
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class AuthContextTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.company_id = str(uuid.uuid4())
        self.location_id = str(uuid.uuid4())
        self.employee_id = str(uuid.uuid4())
        with self.Session() as db:
            db.add(Company(id=self.company_id, name="Test", code="AUTH-CONTEXT", password_hash=hash_secret("pw"), active=True))
            db.add(Location(id=self.location_id, company_id=self.company_id, name="Store", store_number="1000", active=True))
            db.add(Employee(id=self.employee_id, company_id=self.company_id, name="Worker", pin_hash=hash_secret("1234"), role="employee", location_ids=[self.location_id], active=True, auth_version=3))
            db.commit()

    def tearDown(self):
        self.engine.dispose()

    def claims(self, **overrides):
        claims = {"type":"employee","company_id":self.company_id,"employee_id":self.employee_id,"location_id":self.location_id,"auth_version":3,"role":"employee"}
        claims.update(overrides)
        return claims

    def test_context_uses_current_database_role(self):
        with self.Session() as db:
            employee = db.get(Employee, self.employee_id)
            employee.role = "supervisor"
            db.commit()
            context = resolve_employee_context(db, self.claims(role="employee"))
            self.assertEqual(context.role, "supervisor")

    def test_context_rejects_auth_version_mismatch(self):
        with self.Session() as db, self.assertRaises(HTTPException) as caught:
            resolve_employee_context(db, self.claims(auth_version=2))
        self.assertEqual(caught.exception.status_code, 401)

    def test_context_rejects_inactive_company(self):
        with self.Session() as db:
            db.get(Company, self.company_id).active = False
            db.commit()
            with self.assertRaises(HTTPException) as caught:
                resolve_employee_context(db, self.claims())
        self.assertEqual(caught.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
