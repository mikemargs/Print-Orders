from __future__ import annotations

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC)


DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./data/multistore_server.db")
if DATABASE_URL.startswith("sqlite"):
    Path("data").mkdir(exist_ok=True)
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    store_number: Mapped[str] = mapped_column(String(30))
    timezone: Mapped[str] = mapped_column(String(80), default="America/New_York")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    pin_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="employee")
    location_ids: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_by: Mapped[str] = mapped_column(String(36), default="")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    company: Mapped[str] = mapped_column(String(180), default="")
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str] = mapped_column(String(60), default="")
    email: Mapped[str] = mapped_column(String(180), default="")
    address1: Mapped[str] = mapped_column(String(180), default="")
    address2: Mapped[str] = mapped_column(String(180), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    state: Mapped[str] = mapped_column(String(60), default="")
    postal_code: Mapped[str] = mapped_column(String(30), default="")
    tax_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_by: Mapped[str] = mapped_column(String(36), default="")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    order_number: Mapped[str] = mapped_column(String(70), index=True)
    status: Mapped[str] = mapped_column(String(50), default="New", index=True)
    priority: Mapped[str] = mapped_column(String(30), default="Normal")
    received_date: Mapped[str] = mapped_column(String(10), default="")
    due_date: Mapped[str] = mapped_column(String(10), default="", index=True)
    assigned_to: Mapped[str] = mapped_column(String(120), default="")
    delivery_method: Mapped[str] = mapped_column(String(50), default="Pickup")
    po_number: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(String(300), default="")
    artwork_path: Mapped[str] = mapped_column(Text, default="")
    production_notes: Mapped[str] = mapped_column(Text, default="")
    customer_notes: Mapped[str] = mapped_column(Text, default="")
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    deposit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount_mode: Mapped[str] = mapped_column(String(10), default="amount")
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    items: Mapped[list] = mapped_column(JSON, default=list)


class ArtworkFile(Base):
    __tablename__ = "artwork_files"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("work_orders.id"), index=True)
    object_key: Mapped[str] = mapped_column(Text, unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    uploaded_by: Mapped[str] = mapped_column(String(36), default="")
    checksum: Mapped[str] = mapped_column(String(128), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)



class SyncEvent(Base):
    __tablename__ = "sync_events"
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(36))
    change_type: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProcessedOperation(Base):
    __tablename__ = "processed_operations"
    __table_args__ = (UniqueConstraint("company_id", "operation_id", name="uq_processed_operation_company_operation"),)
    row_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(36))
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CustomerIssue(Base):
    __tablename__ = 'customer_issues'
    __table_args__ = (UniqueConstraint('company_id', 'reference', name='uq_issue_company_reference'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id'), index=True)
    location_id: Mapped[str] = mapped_column(ForeignKey('locations.id'), index=True)
    reference: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40), default='Customer Service')
    priority: Mapped[str] = mapped_column(String(20), default='Normal')
    status: Mapped[str] = mapped_column(String(40), default='Open', index=True)
    assigned_employee_id: Mapped[str | None] = mapped_column(ForeignKey('employees.id'), nullable=True, index=True)
    work_order_id: Mapped[str | None] = mapped_column(ForeignKey('work_orders.id'), nullable=True)
    next_action: Mapped[str] = mapped_column(Text, default='')
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    resolution_summary: Mapped[str] = mapped_column(Text, default='')
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(36))
    updated_by: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IssueActivity(Base):
    __tablename__ = 'issue_activities'
    __table_args__ = (UniqueConstraint('company_id', 'operation_id', name='uq_issue_activity_operation'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey('companies.id'), index=True)
    issue_id: Mapped[str] = mapped_column(ForeignKey('customer_issues.id'), index=True)
    activity_type: Mapped[str] = mapped_column(String(30))
    channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    author_employee_id: Mapped[str] = mapped_column(ForeignKey('employees.id'))
    author_name: Mapped[str] = mapped_column(String(120))
    summary: Mapped[str] = mapped_column(Text)
    changed_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)

Index("ix_issue_company_store_status", CustomerIssue.company_id, CustomerIssue.location_id, CustomerIssue.status)
Index("ix_issue_activity_timeline", IssueActivity.issue_id, IssueActivity.occurred_at, IssueActivity.recorded_at)
