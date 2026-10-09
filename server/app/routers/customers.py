from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import Customer, CustomerIssue, Mailbox, OperationalTask, ShippingCase, WorkOrder
from ..schemas.api import CustomerCreate, CustomerUpdate, VersionBody
from ..services.common import Conflict, Forbidden, Invalid
from ..services.drilldowns import apply_view
from ..services.records import create_or_update_customer, delete_customer, serialize_record
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router = APIRouter(prefix='/api/customers', tags=['customers'])

def service_error(exc):
    if isinstance(exc, Conflict): return JSONResponse(status_code=409, content={'detail':str(exc),'current':exc.current})
    if isinstance(exc, Forbidden): raise HTTPException(403,str(exc))
    if isinstance(exc, Invalid): raise HTTPException(400,str(exc))
    raise exc

@router.get('')
def list_customers(search: str='', limit: int=Query(50,ge=1,le=200), offset: int=Query(0,ge=0), auth=Depends(web_auth_context), db: Session=Depends(get_web_db)):
    q=select(Customer).where(Customer.company_id==auth.company_id, Customer.is_deleted.is_(False))
    if search.strip():
        needle=f"%{search.strip()}%"
        q=q.where(or_(Customer.company.ilike(needle),Customer.first_name.ilike(needle),Customer.last_name.ilike(needle),Customer.phone.ilike(needle),Customer.email.ilike(needle)))
    rows=db.scalars(q.order_by(Customer.company,Customer.last_name).offset(offset).limit(limit)).all()
    return {'customers':[serialize_record(x) for x in rows]}

@router.post('', status_code=201)
def create_customer(body: CustomerCreate, auth=Depends(web_mutation_context), db: Session=Depends(get_web_db)):
    try:
        row=create_or_update_customer(db,auth,str(uuid.uuid4()),0,body.model_dump())
        db.commit(); return serialize_record(row)
    except Exception as exc:
        db.rollback(); return service_error(exc)

@router.get('/{customer_id}/summary')
def customer_summary(customer_id: str, auth=Depends(web_auth_context), db: Session=Depends(get_web_db)):
    customer = db.get(Customer, customer_id)
    if not customer or customer.company_id != auth.company_id or customer.is_deleted:
        raise HTTPException(404, 'Customer not found')
    result = {}
    for key, model, view in [
        ('active_orders', WorkOrder, 'pending'), ('all_orders', WorkOrder, 'all'),
        ('open_issues', CustomerIssue, 'open'), ('open_tasks', OperationalTask, 'open'),
        ('active_mailboxes', Mailbox, 'active'), ('open_shipping', ShippingCase, 'open'),
    ]:
        query = select(model).where(model.company_id == auth.company_id, model.customer_id == customer_id)
        if model is WorkOrder:
            query = query.where(WorkOrder.is_deleted.is_(False))
        query = apply_view(db, auth, query, model, view)
        result[key] = db.scalar(select(func.count()).select_from(query.subquery()))
    return result

@router.get('/{customer_id}')
def get_customer(customer_id: str, auth=Depends(web_auth_context), db: Session=Depends(get_web_db)):
    row=db.get(Customer,customer_id)
    if not row or row.company_id!=auth.company_id or row.is_deleted: raise HTTPException(404,'Customer not found')
    return serialize_record(row)

@router.patch('/{customer_id}')
def update_customer(customer_id: str, body: CustomerUpdate, auth=Depends(web_mutation_context), db: Session=Depends(get_web_db)):
    data=body.model_dump(exclude_unset=True); version=data.pop('version')
    try:
        row=create_or_update_customer(db,auth,customer_id,version,data); db.commit(); return serialize_record(row)
    except Exception as exc:
        db.rollback(); return service_error(exc)

@router.delete('/{customer_id}')
def remove_customer(customer_id: str, body: VersionBody, auth=Depends(web_mutation_context), db: Session=Depends(get_web_db)):
    try:
        row=delete_customer(db,auth,customer_id,body.version); db.commit(); return {'deleted':True,'current':serialize_record(row) if row else None}
    except Exception as exc:
        db.rollback(); return service_error(exc)
