import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from app.auth_context import AuthContext
from app.database import (
    Base,
    Company,
    Customer,
    CustomerIssue,
    Employee,
    IssueActivity,
    Location,
    WorkOrder,
)
from app.services.common import Conflict, Forbidden, Invalid, NotFound
from app.services.issues import append_communication, create_issue, serialize_issue, update_issue


class IssueServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.auth = AuthContext("co", "e", "employee", "l", 1)
        self.admin = AuthContext("co", "e", "admin", "l", 1)
        with self.Session() as db:
            db.add_all(
                [
                    Company(id="co", name="C", code="C", password_hash="x"),
                    Company(id="other", name="O", code="O", password_hash="x"),
                ]
            )
            db.flush()
            db.add_all(
                [
                    Location(id="l", company_id="co", name="Sayville", store_number="5127"),
                    Location(id="l2", company_id="co", name="Selden", store_number="5345"),
                    Location(id="foreign", company_id="other", name="Other", store_number="1"),
                    Employee(
                        id="e", company_id="co", name="Nick", pin_hash="x", location_ids=["l"]
                    ),
                    Employee(id="other-e", company_id="other", name="Other", pin_hash="x"),
                    Customer(id="c", company_id="co", first_name="Test"),
                    Customer(id="c2", company_id="co"),
                    Customer(id="foreign-c", company_id="other"),
                ]
            )
            db.flush()
            db.add(
                WorkOrder(
                    id="w", company_id="co", customer_id="c", location_id="l", order_number="WO-1"
                )
            )
            db.commit()
        self.base = {
            "customer_id": "c",
            "location_id": "l",
            "title": "Wrong package",
            "description": "Customer reports issue",
        }

    def tearDown(self):
        self.engine.dispose()

    def issue(self, db, **changes):
        return create_issue(db, self.auth, self.base | changes)

    def test_create_and_serialize_with_author_and_history(self):
        with self.Session() as db:
            row = self.issue(db, assigned_employee_id="e", work_order_id="w")
            db.commit()
            data = serialize_issue(db, row)
            self.assertEqual(data["customer"]["first_name"], "Test")
            self.assertEqual(data["store"]["name"], "Sayville")
            self.assertEqual(row.status, "Open")
            self.assertEqual(row.created_by, "e")
            self.assertEqual(db.scalar(select(func.count()).select_from(IssueActivity)), 1)

    def test_company_store_and_link_validation(self):
        with self.Session() as db:
            for change in [
                {"customer_id": "foreign-c"},
                {"location_id": "foreign"},
                {"assigned_employee_id": "other-e"},
                {"customer_id": "c2", "work_order_id": "w"},
            ]:
                with self.subTest(change=change), self.assertRaises((Invalid, Forbidden)):
                    self.issue(db, **change)
            with self.assertRaises(Forbidden):
                self.issue(db, location_id="l2")
            row = create_issue(db, self.admin, self.base | {"location_id": "l2"})
            db.commit()
            with self.assertRaises(Forbidden):
                update_issue(db, self.auth, row.id, 1, {"title": "change"})
            with self.assertRaises(Invalid):
                update_issue(db, self.admin, row.id, 1, {"assigned_employee_id": "e"})

    def test_resolve_reopen_and_nonblank_reason(self):
        with self.Session() as db:
            row = self.issue(db)
            db.commit()
            with self.assertRaises(Invalid):
                update_issue(db, self.auth, row.id, 1, {"status": "Resolved"})
            row = update_issue(
                db,
                self.auth,
                row.id,
                1,
                {"status": "Resolved", "resolution_summary": "Replacement supplied"},
            )
            db.commit()
            self.assertIsNotNone(row.resolved_at)
            with self.assertRaises(Invalid):
                update_issue(db, self.auth, row.id, 2, {"status": "Open"})
            row = update_issue(
                db,
                self.auth,
                row.id,
                2,
                {"status": "Open", "reopen_reason": "Customer needs further help"},
            )
            db.commit()
            self.assertIsNone(row.resolved_at)
            self.assertEqual(row.version, 3)
            entries = db.scalars(
                select(IssueActivity).where(IssueActivity.issue_id == row.id)
            ).all()
            self.assertEqual(len(entries), 3)
            self.assertTrue(any("Replacement supplied" in str(x.changed_fields) for x in entries))

    def test_stale_version_does_not_add_history_or_overwrite(self):
        with self.Session() as a, self.Session() as b:
            row = self.issue(a)
            a.commit()
            stale = b.get(CustomerIssue, row.id)
            update_issue(a, self.auth, row.id, 1, {"title": "New title"})
            a.commit()
            with self.assertRaises(Conflict):
                update_issue(b, self.auth, stale.id, 1, {"title": "Lost title"})
            b.rollback()
            b.expire_all()
            self.assertEqual(b.get(CustomerIssue, row.id).title, "New title")
            self.assertEqual(b.scalar(select(func.count()).select_from(IssueActivity)), 2)

    def test_incompatible_retained_order_rejected(self):
        with self.Session() as db:
            row = self.issue(db, work_order_id="w")
            db.commit()
            with self.assertRaises(Invalid):
                update_issue(db, self.auth, row.id, 1, {"customer_id": "c2"})
            row = update_issue(
                db, self.auth, row.id, 1, {"customer_id": "c2", "work_order_id": None}
            )
            db.commit()
            self.assertIsNone(row.work_order_id)

    def test_log_idempotent_and_conflicting_reuse(self):
        with self.Session() as db:
            row = self.issue(db)
            db.commit()
            payload = {
                "operation_id": str(uuid4()),
                "channel": "email",
                "occurred_at": datetime.now(UTC),
                "summary": "Customer's <script>literal note</script>",
                "version": 1,
                "next_action": "Call tomorrow",
            }
            first = append_communication(db, self.auth, row.id, payload)
            db.commit()
            second = append_communication(db, self.auth, row.id, payload)
            db.commit()
            self.assertEqual(first.id, second.id)
            self.assertEqual(first.author_name, "Nick")
            db.refresh(row)
            self.assertEqual(row.version, 2)
            with self.assertRaises(Conflict):
                append_communication(db, self.auth, row.id, payload | {"summary": "changed"})
            self.assertEqual(
                db.scalar(
                    select(func.count())
                    .select_from(IssueActivity)
                    .where(IssueActivity.activity_type == "communication")
                ),
                1,
            )

    def test_conflicting_log_followup_rolls_back(self):
        with self.Session() as db:
            row = self.issue(db)
            db.commit()
            update_issue(db, self.auth, row.id, 1, {"title": "Changed"})
            db.commit()
            with self.assertRaises(Conflict):
                append_communication(
                    db,
                    self.auth,
                    row.id,
                    {
                        "operation_id": str(uuid4()),
                        "channel": "phone",
                        "occurred_at": datetime.now(UTC),
                        "summary": "Call",
                        "version": 1,
                        "next_action": "Next",
                    },
                )
            db.rollback()
            self.assertEqual(
                db.scalar(
                    select(func.count())
                    .select_from(IssueActivity)
                    .where(IssueActivity.activity_type == "communication")
                ),
                0,
            )

    def test_unknown_or_foreign_case_not_found(self):
        with self.Session() as db:
            row = self.issue(db)
            db.commit()
            with self.assertRaises(NotFound):
                update_issue(
                    db,
                    AuthContext("other", "other-e", "admin", "foreign", 1),
                    row.id,
                    1,
                    {"title": "Spoof"},
                )

    def test_inactive_assignee_or_customer_rejected(self):
        with self.Session() as db:
            db.get(Employee, "e").active = False
            db.commit()
            with self.assertRaises(Invalid):
                self.issue(db, assigned_employee_id="e")
            db.get(Customer, "c").is_deleted = True
            db.commit()
            with self.assertRaises(Invalid):
                self.issue(db)
