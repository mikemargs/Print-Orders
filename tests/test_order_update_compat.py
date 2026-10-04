import os
import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("JWT_SECRET", "schema-test-secret-that-is-longer-than-thirty-two")
sys.path.insert(0, str(ROOT / "server"))

from app.schemas.api import OrderUpdate


class OrderUpdateCompatibilityTests(unittest.TestCase):
    def test_known_server_managed_fields_are_accepted_but_excluded(self):
        payload = {
            "version": 2,
            "customer_id": "customer-1",
            "total": 52.03,
            "subtotal": 47.9,
            "balance": 52.03,
            "id": "order-1",
            "is_deleted": False,
            "updated_at": "2026-10-03T23:53:51.700690+00:00",
            "updated_by": "employee-1",
        }

        parsed = OrderUpdate.model_validate(payload)
        dumped = parsed.model_dump(exclude_unset=True)

        self.assertEqual(dumped, {"version": 2, "customer_id": "customer-1"})

    def test_unrelated_extra_fields_are_still_rejected(self):
        with self.assertRaises(ValidationError):
            OrderUpdate.model_validate({"version": 2, "unexpected": "nope"})


if __name__ == "__main__":
    unittest.main()
