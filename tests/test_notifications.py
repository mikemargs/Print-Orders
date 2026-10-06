import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import BackgroundTasks

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app.database import Customer, CustomerIssue, Employee, Location, WorkOrder
from app.services.notifications import (
    queue_customer_issue_created,
    queue_work_order_created,
    recipients_for_store,
    send_notification,
)


class FakeDb:
    def __init__(self, rows):
        self.rows = rows

    def get(self, model, row_id):
        return self.rows.get((model, row_id))


class NotificationTests(unittest.TestCase):
    def test_store_recipient_and_management_recipient_are_combined_and_deduped(self):
        with patch.dict(
            os.environ,
            {
                "NOTIFY_EMAIL_SAYVILLE": "sayville@example.com, manager@example.com",
                "NOTIFY_EMAIL_ADDITIONAL": "manager@example.com; owner@example.com",
            },
            clear=False,
        ):
            self.assertEqual(
                recipients_for_store("5127"),
                ["sayville@example.com", "manager@example.com", "owner@example.com"],
            )

    @patch("app.services.notifications.httpx.post")
    def test_resend_request_uses_store_recipient_and_idempotency(self, post):
        response = Mock()
        response.raise_for_status.return_value = None
        post.return_value = response
        with patch.dict(
            os.environ,
            {
                "RESEND_API_KEY": "re_test",
                "NOTIFICATION_EMAIL_FROM": "Print Orders <notify@example.com>",
                "NOTIFY_EMAIL_SELDEN": "selden@example.com",
                "NOTIFY_EMAIL_ADDITIONAL": "",
                "PUBLIC_APP_URL": "https://orders.example.com/",
            },
            clear=False,
        ):
            send_notification(
                event_type="work-order-created",
                entity_id="order-1",
                store_number="5345",
                subject="New work order",
                lines=["Store: Selden #5345", "Order: WO-1"],
                path="/orders/order-1",
            )

        post.assert_called_once()
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["to"], ["selden@example.com"])
        self.assertEqual(kwargs["json"]["from"], "Print Orders <notify@example.com>")
        self.assertIn("https://orders.example.com/orders/order-1", kwargs["json"]["text"])
        self.assertEqual(
            kwargs["headers"]["Idempotency-Key"], "work-order-created/order-1"
        )
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer re_test")

    @patch("app.services.notifications.httpx.post")
    def test_email_failure_is_swallowed(self, post):
        post.side_effect = RuntimeError("provider unavailable")
        with patch.dict(
            os.environ,
            {
                "RESEND_API_KEY": "re_test",
                "NOTIFICATION_EMAIL_FROM": "notify@example.com",
                "NOTIFY_EMAIL_MT_SINAI": "mtsinai@example.com",
            },
            clear=False,
        ):
            send_notification(
                event_type="customer-issue-created",
                entity_id="issue-1",
                store_number="3167",
                subject="New issue",
                lines=["Issue"],
                path="/issues/issue-1",
            )
        post.assert_called_once()

    def test_work_order_queue_targets_the_orders_page_for_its_store(self):
        company_id = "co"
        location = Location(
            id="loc", company_id=company_id, name="Sayville", store_number="5127"
        )
        customer = Customer(
            id="cust",
            company_id=company_id,
            company="Acme",
            first_name="Pat",
            last_name="Tester",
        )
        employee = Employee(
            id="emp",
            company_id=company_id,
            name="Alex",
            pin_hash="x",
            role="employee",
            location_ids=["loc"],
        )
        order = WorkOrder(
            id="order",
            company_id=company_id,
            customer_id="cust",
            location_id="loc",
            order_number="WO-5127-TEST",
            status="New",
            priority="Rush",
            due_date="2026-10-10",
            description="Banner",
            total=25,
        )
        db = FakeDb(
            {
                (Location, "loc"): location,
                (Customer, "cust"): customer,
                (Employee, "emp"): employee,
            }
        )
        background = BackgroundTasks()
        queue_work_order_created(background, db, order, "emp")
        self.assertEqual(len(background.tasks), 1)
        task = background.tasks[0]
        self.assertEqual(task.kwargs["store_number"], "5127")
        self.assertEqual(task.kwargs["path"], "/orders/order")
        self.assertIn("WO-5127-TEST", task.kwargs["subject"])
        self.assertTrue(any(line == "Created by: Alex" for line in task.kwargs["lines"]))

    def test_customer_issue_queue_targets_the_issue_page_for_its_store(self):
        company_id = "co"
        location = Location(
            id="loc", company_id=company_id, name="Selden", store_number="5345"
        )
        customer = Customer(id="cust", company_id=company_id, first_name="Pat")
        employee = Employee(
            id="emp",
            company_id=company_id,
            name="Alex",
            pin_hash="x",
            role="employee",
            location_ids=["loc"],
        )
        issue = CustomerIssue(
            id="issue",
            company_id=company_id,
            customer_id="cust",
            location_id="loc",
            reference="CI-123",
            title="Complaint",
            description="Package problem",
            category="Shipping",
            priority="High",
            status="Open",
            created_by="emp",
            updated_by="emp",
        )
        db = FakeDb(
            {
                (Location, "loc"): location,
                (Customer, "cust"): customer,
                (Employee, "emp"): employee,
            }
        )
        background = BackgroundTasks()
        queue_customer_issue_created(background, db, issue, "emp")
        self.assertEqual(len(background.tasks), 1)
        task = background.tasks[0]
        self.assertEqual(task.kwargs["store_number"], "5345")
        self.assertEqual(task.kwargs["path"], "/issues/issue")
        self.assertIn("CI-123", task.kwargs["subject"])


if __name__ == "__main__":
    unittest.main()
