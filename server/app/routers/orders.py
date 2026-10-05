from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import ArtworkFile, Customer, WorkOrder
from ..schemas.api import OrderCreate, OrderUpdate, VersionBody
from ..services.common import Conflict, Forbidden, Invalid
from ..services.records import create_or_update_order, delete_order, serialize_record
from ..web_sessions import get_web_db, web_auth_context, web_mutation_context

router=APIRouter(prefix='/api/orders',tags=['orders'])

def service_error(exc):
    if isinstance(exc, Conflict): return JSONResponse(status_code=409, content={'detail':str(exc),'current':exc.current})
    if isinstance(exc, Forbidden): raise HTTPException(403,str(exc))
    if isinstance(exc, Invalid): raise HTTPException(400,str(exc))
    raise exc

@router.get('')
def list_orders(search: str='', location_id: str='', status: str='', priority: str='', customer_id: str='', due_start: date | None=None, due_end: date | None=None, limit: int=Query(100,ge=1,le=250), offset: int=Query(0,ge=0), auth=Depends(web_auth_context), db: Session=Depends(get_web_db)):
    q=select(WorkOrder).where(WorkOrder.company_id==auth.company_id,WorkOrder.is_deleted.is_(False))
    if location_id: q=q.where(WorkOrder.location_id==location_id)
    if status: q=q.where(WorkOrder.status==status)
    if priority: q=q.where(WorkOrder.priority==priority)
    if customer_id: q=q.where(WorkOrder.customer_id==customer_id)
    if due_start: q=q.where(WorkOrder.due_date>=due_start.isoformat())
    if due_end: q=q.where(WorkOrder.due_date<=due_end.isoformat())
    if search.strip():
        needle=f"%{search.strip()}%"
        q=q.join(Customer,Customer.id==WorkOrder.customer_id).where(or_(WorkOrder.order_number.ilike(needle),WorkOrder.description.ilike(needle),Customer.company.ilike(needle),Customer.first_name.ilike(needle),Customer.last_name.ilike(needle)))
    rows=db.scalars(q.order_by(WorkOrder.due_date,WorkOrder.updated_at.desc()).offset(offset).limit(limit)).all()
    order_ids=[row.id for row in rows]
    artwork_order_ids=set()
    if order_ids:
        artwork_order_ids=set(db.scalars(
            select(ArtworkFile.work_order_id).where(
                ArtworkFile.company_id==auth.company_id,
                ArtworkFile.work_order_id.in_(order_ids),
                ArtworkFile.active.is_(True),
                ArtworkFile.deleted.is_(False),
            )
        ).all())
    serialized=[]
    for row in rows:
        payload=serialize_record(row)
        payload['has_artwork']=row.id in artwork_order_ids
        serialized.append(payload)
    return {'orders':serialized}

@router.post('',status_code=201)
def create_order(body: OrderCreate, auth=Depends(web_mutation_context), db: Session=Depends(get_web_db)):
    try:
        row=create_or_update_order(db,auth,str(uuid.uuid4()),0,body.model_dump()); db.commit(); return serialize_record(row)
    except Exception as exc:
        db.rollback(); return service_error(exc)

@router.get('/{order_id}')
def get_order(order_id: str, auth=Depends(web_auth_context), db: Session=Depends(get_web_db)):
    row=db.get(WorkOrder,order_id)
    if not row or row.company_id!=auth.company_id or row.is_deleted: raise HTTPException(404,'Work order not found')
    return serialize_record(row)

@router.patch('/{order_id}')
def update_order(order_id: str, body: OrderUpdate, auth=Depends(web_mutation_context), db: Session=Depends(get_web_db)):
    data=body.model_dump(exclude_unset=True); version=data.pop('version')
    try:
        row=create_or_update_order(db,auth,order_id,version,data); db.commit(); return serialize_record(row)
    except Exception as exc:
        db.rollback(); return service_error(exc)

@router.delete('/{order_id}')
def remove_order(order_id: str, body: VersionBody, auth=Depends(web_mutation_context), db: Session=Depends(get_web_db)):
    try:
        row=delete_order(db,auth,order_id,body.version); db.commit(); return {'deleted':True,'current':serialize_record(row) if row else None}
    except Exception as exc:
        db.rollback(); return service_error(exc)
