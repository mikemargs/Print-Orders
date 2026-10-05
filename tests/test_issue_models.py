import sys
import unittest
from pathlib import Path
from datetime import UTC, datetime
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from app.database import Base, CustomerIssue, IssueActivity
from app.schemas.issues import IssueCreate, IssueUpdate, CommunicationCreate

class IssueModelTests(unittest.TestCase):
    def test_schema_validates_text_enums_dates_and_extra_fields(self):
        base = dict(customer_id='c', location_id='l', title=' Test ', description=' Details ')
        issue = IssueCreate(**base)
        self.assertEqual(issue.title, 'Test')
        self.assertIsNone(issue.work_order_id)
        self.assertIsNone(issue.assigned_employee_id)
        for change in ({'title':' '}, {'description':''}, {'title':'x'*201}, {'category':'Bad'}, {'priority':'Bad'}, {'follow_up_date':'2026-02-30'}, {'created_by':'spoof'}):
            with self.subTest(change=change), self.assertRaises(ValidationError): IssueCreate(**(base | change))
        with self.assertRaises(ValidationError): IssueUpdate(version=1,status='Resolved',resolution_summary=' ')
        with self.assertRaises(ValidationError): IssueUpdate(version=1,title=None)
        with self.assertRaises(ValidationError): IssueUpdate(version=1,status='Open',reopen_reason=' ')
        with self.assertRaises(ValidationError): CommunicationCreate(operation_id='not-uuid',channel='email',occurred_at=datetime.now(UTC),summary='hello')
        with self.assertRaises(ValidationError): CommunicationCreate(operation_id='00000000-0000-0000-0000-000000000001',channel='phone',occurred_at=datetime.now(),summary='hello')

    def test_unique_references_and_operation_ids(self):
        engine=create_engine('sqlite:///:memory:'); Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add(CustomerIssue(id='i',company_id='c',customer_id='u',location_id='l',reference='CI-one',title='A',description='B',created_by='e',updated_by='e'))
            db.commit()
            db.add(CustomerIssue(id='j',company_id='c',customer_id='u',location_id='l',reference='CI-one',title='A',description='B',created_by='e',updated_by='e'))
            with self.assertRaises(IntegrityError): db.commit()
            db.rollback()
            for id in ['a','b']:
                db.add(IssueActivity(id=id,company_id='c',issue_id='i',activity_type='communication',channel='phone',occurred_at=datetime.now(UTC),author_employee_id='e',author_name='Employee',summary='Note',operation_id='same',request_payload={}))
                if id=='a': db.commit()
            with self.assertRaises(IntegrityError): db.commit()
        engine.dispose()
