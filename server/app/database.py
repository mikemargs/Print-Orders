from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
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
    tax_rate: Mapped[float] = mapped_column(Float, default=0)
    deposit: Mapped[float] = mapped_column(Float, default=0)
    discount: Mapped[float] = mapped_column(Float, default=0)
    subtotal: Mapped[float] = mapped_column(Float, default=0)
    total: Mapped[float] = mapped_column(Float, default=0)
    balance: Mapped[float] = mapped_column(Float, default=0)
    items: Mapped[list] = mapped_column(JSON, default=list)


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
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
