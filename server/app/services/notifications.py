from __future__ import annotations

import html
import logging
import os
from collections.abc import Iterable
from decimal import Decimal

import httpx
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from ..database import Customer, CustomerIssue, Employee, Location, WorkOrder

logger = logging.getLogger(__name__)

RESEND_EMAILS_URL = "https://api.resend.com/emails"

STORE_RECIPIENT_ENV = {
    "5127": "NOTIFY_EMAIL_SAYVILLE",
    "5345": "NOTIFY_EMAIL_SELDEN",
    "3167": "NOTIFY_EMAIL_MT_SINAI",
}


def _split_addresses(value: str) -> list[str]:
    normalized = value.replace(";", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def _dedupe(addresses: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for address in addresses:
        key = address.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(address)
    return result


def recipients_for_store(store_number: str) -> list[str]:
    store_key = STORE_RECIPIENT_ENV.get(store_number, f"NOTIFY_EMAIL_STORE_{store_number}")
    return _dedupe(
        _split_addresses(os.environ.get(store_key, ""))
        + _split_addresses(os.environ.get("NOTIFY_EMAIL_ADDITIONAL", ""))
    )


def _customer_name(customer: Customer | None) -> str:
    if customer is None:
        return "Unknown customer"
    company = (customer.company or "").strip()
    person = " ".join(
        part.strip() for part in (customer.first_name or "", customer.last_name or "") if part.strip()
    )
    if company and person:
        return f"{company} ({person})"
    return company or person or "Unnamed customer"


def _money(value) -> str:
    try:
        return f"${Decimal(value):,.2f}"
    except Exception:
        return "$0.00"


def _public_url(path: str) -> str:
    base = (
        os.environ.get("PUBLIC_APP_URL", "").strip()
        or os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    )
    return f"{base.rstrip('/')}{path}" if base else ""


def _html_body(lines: list[str], link: str) -> str:
    paragraphs = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    if link:
        paragraphs += (
            '<p><a href="'
            + html.escape(link, quote=True)
            + '">Open in Print Order Manager</a></p>'
        )
    return (
        '<div style="font-family:Arial,sans-serif;line-height:1.45;color:#17324d">'
        + paragraphs
        + "</div>"
    )


def send_notification(
    *,
    event_type: str,
    entity_id: str,
    store_number: str,
    subject: str,
    lines: list[str],
    path: str,
) -> None:
    recipients = recipients_for_store(store_number)
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    sender = os.environ.get("NOTIFICATION_EMAIL_FROM", "").strip()
    if not recipients or not api_key or not sender:
        return

    link = _public_url(path)
    text_body = "\n".join(lines + ([f"Open: {link}"] if link else []))
    payload = {
        "from": sender,
        "to": recipients,
        "subject": subject,
        "text": text_body,
        "html": _html_body(lines, link),
    }
    try:
        response = httpx.post(
            RESEND_EMAILS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": f"{event_type}/{entity_id}",
            },
            json=payload,
            timeout=10.0,
        )
        response.raise_for_status()
    except Exception:
        logger.exception(
            "Internal email notification failed for %s %s at store %s",
            event_type,
            entity_id,
            store_number,
        )


def queue_work_order_created(
    background_tasks: BackgroundTasks,
    db: Session,
    order: WorkOrder,
    employee_id: str,
) -> None:
    try:
        location = db.get(Location, order.location_id)
        if not location or location.company_id != order.company_id:
            return
        customer = db.get(Customer, order.customer_id)
        if customer and customer.company_id != order.company_id:
            customer = None
        employee = db.get(Employee, employee_id)
        creator = (
            employee.name
            if employee and employee.company_id == order.company_id
            else "Unknown employee"
        )
        store_label = f"{location.name} #{location.store_number}"
        lines = [
            "A new work order was created.",
            f"Store: {store_label}",
            f"Order: {order.order_number}",
            f"Customer: {_customer_name(customer)}",
            f"Status: {order.status}",
            f"Priority: {order.priority}",
            f"Due date: {order.due_date or 'Not set'}",
            f"Description: {order.description or 'No description'}",
            f"Total: {_money(order.total)}",
            f"Created by: {creator}",
        ]
        background_tasks.add_task(
            send_notification,
            event_type="work-order-created",
            entity_id=order.id,
            store_number=location.store_number,
            subject=f"[{store_label}] New Work Order {order.order_number}",
            lines=lines,
            path=f"/orders/{order.id}",
        )
    except Exception:
        logger.exception("Unable to queue work order notification for %s", order.id)


def queue_customer_issue_created(
    background_tasks: BackgroundTasks,
    db: Session,
    issue: CustomerIssue,
    employee_id: str,
) -> None:
    try:
        location = db.get(Location, issue.location_id)
        if not location or location.company_id != issue.company_id:
            return
        customer = db.get(Customer, issue.customer_id)
        if customer and customer.company_id != issue.company_id:
            customer = None
        employee = db.get(Employee, employee_id)
        creator = (
            employee.name
            if employee and employee.company_id == issue.company_id
            else "Unknown employee"
        )
        store_label = f"{location.name} #{location.store_number}"
        lines = [
            "A new customer issue was created.",
            f"Store: {store_label}",
            f"Case: {issue.reference}",
            f"Customer: {_customer_name(customer)}",
            f"Title: {issue.title}",
            f"Category: {issue.category}",
            f"Priority: {issue.priority}",
            f"Status: {issue.status}",
            f"Follow-up date: {issue.follow_up_date.isoformat() if issue.follow_up_date else 'Not set'}",
            f"Next action: {issue.next_action or 'Not set'}",
            f"Description: {issue.description}",
            f"Created by: {creator}",
        ]
        background_tasks.add_task(
            send_notification,
            event_type="customer-issue-created",
            entity_id=issue.id,
            store_number=location.store_number,
            subject=f"[{store_label}] New Customer Issue {issue.reference}",
            lines=lines,
            path=f"/issues/{issue.id}",
        )
    except Exception:
        logger.exception("Unable to queue customer issue notification for %s", issue.id)
