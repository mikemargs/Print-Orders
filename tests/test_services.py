import sys
import unittest
import uuid
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from app.auth_context import AuthContext
from app.database import Base, Company, Location, SyncEvent
from app.services.common import Conflict, Forbidden, Invalid
from app.services.records import create_or_update_customer, create_or_update_order, delete_customer


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.company = str(uuid.uuid4()); self.location = str(uuid.uuid4()); self.employee = str(uuid.uuid4())
        with self.Session() as db:
            db.add(Company(id=self.company,name='Test',code='SVC',password_hash='x',active=True))
            db.add(Location(id=self.location,company_id=self.company,name='Store',store_number='1',active=True))
            db.commit()
        self.auth = AuthContext(self.company,self.employee,'admin',self.location,1)

    def tearDown(self): self.engine.dispose()

    def test_customer_mutation_emits_exactly_one_event_and_conflicts_stale_version(self):
        cid=str(uuid.uuid4())
        with self.Session() as db:
            customer=create_or_update_customer(db,self.auth,cid,0,{'company':'One'}); db.commit()
            self.assertEqual(customer.version,1)
            self.assertEqual(db.scalar(select(func.count()).select_from(SyncEvent)),1)
            with self.assertRaises(Conflict): create_or_update_customer(db,self.auth,cid,0,{'company':'Stale'})

    def test_order_service_calculates_total_and_enforces_store(self):
        cid=str(uuid.uuid4()); oid=str(uuid.uuid4())
        with self.Session() as db:
            create_or_update_customer(db,self.auth,cid,0,{'company':'C'})
            order=create_or_update_order(db,self.auth,oid,0,{'customer_id':cid,'location_id':self.location,'status':'New','priority':'Normal','received_date':'2026-10-03','tax_rate':8.625,'items':[{'item_name':'P','quantity':1,'unit_price':100}]})
            self.assertEqual(float(order.total),108.63)

    def test_order_service_rejects_non_numeric_money_fields(self):
        cid = str(uuid.uuid4())
        with self.Session() as db:
            create_or_update_customer(db, self.auth, cid, 0, {'company': 'C'})
            for field in ('tax_rate', 'deposit', 'discount'):
                with self.subTest(field=field), self.assertRaises(Invalid):
                    create_or_update_order(
                        db,
                        self.auth,
                        str(uuid.uuid4()),
                        0,
                        {
                            'customer_id': cid,
                            'location_id': self.location,
                            'status': 'New',
                            'priority': 'Normal',
                            'received_date': '2026-10-03',
                            field: 'not-a-number',
                            'items': [],
                        },
                    )

    def test_services_reject_values_beyond_postgresql_numeric_precision(self):
        with self.Session() as db:
            cid = str(uuid.uuid4())
            create_or_update_customer(db, self.auth, cid, 0, {"company": "C"})
            with self.assertRaises(Invalid):
                create_or_update_order(
                    db,
                    self.auth,
                    str(uuid.uuid4()),
                    0,
                    {
                        "customer_id": cid,
                        "location_id": self.location,
                        "received_date": "2026-10-03",
                        "tax_rate": "1000",
                        "items": [],
                    },
                )

            with self.assertRaises(Invalid):
                create_or_update_order(
                    db,
                    self.auth,
                    str(uuid.uuid4()),
                    0,
                    {
                        "customer_id": cid,
                        "location_id": self.location,
                        "received_date": "2026-10-03",
                        "tax_rate": "0",
                        "items": [
                            {
                                "item_name": "Huge",
                                "quantity": 2,
                                "unit_price": "6000000000",
                            }
                        ],
                    },
                )

    def test_services_reject_non_finite_and_extreme_numeric_payloads(self):
        with self.Session() as db:
            cid = str(uuid.uuid4())
            create_or_update_customer(db, self.auth, cid, 0, {"company": "C"})
            base = {
                "customer_id": cid,
                "location_id": self.location,
                "status": "New",
                "priority": "Normal",
                "received_date": "2026-10-03",
            }
            for field, value in (("tax_rate", "NaN"), ("deposit", "Infinity"), ("discount", "NaN")):
                with self.subTest(field=field), self.assertRaises(Invalid):
                    create_or_update_order(
                        db, self.auth, str(uuid.uuid4()), 0, {**base, field: value, "items": []}
                    )
            with self.assertRaises(Invalid):
                create_or_update_order(
                    db,
                    self.auth,
                    str(uuid.uuid4()),
                    0,
                    {**base, "items": [{"item_name": "Huge", "quantity": "1e100", "unit_price": 1}]},
                )

    def test_services_reject_overlong_and_malformed_text_payloads(self):
        with self.Session() as db:
            with self.assertRaises(Invalid):
                create_or_update_customer(db, self.auth, str(uuid.uuid4()), 0, {'company': 'X' * 181})

            cid = str(uuid.uuid4())
            create_or_update_customer(db, self.auth, cid, 0, {'company': 'C'})
            base = {
                'customer_id': cid,
                'location_id': self.location,
                'status': 'New',
                'priority': 'Normal',
                'received_date': '2026-10-03',
            }
            with self.assertRaises(Invalid):
                create_or_update_order(db, self.auth, str(uuid.uuid4()), 0, {**base, 'description': 'X' * 301})
            with self.assertRaises(Invalid):
                create_or_update_order(db, self.auth, str(uuid.uuid4()), 0, {**base, 'items': ['not-an-object']})
            with self.assertRaises(Invalid):
                create_or_update_order(db, self.auth, str(uuid.uuid4()), 0, {**base, 'items': [{'item_name': 'X' * 201, 'quantity': 1, 'unit_price': 1}]})

    def test_employee_cannot_delete_customer(self):
        cid=str(uuid.uuid4())
        with self.Session() as db:
            create_or_update_customer(db,self.auth,cid,0,{'company':'C'}); db.flush()
            employee_auth=AuthContext(self.company,self.employee,'employee',self.location,1)
            with self.assertRaises(Forbidden): delete_customer(db,employee_auth,cid,1)

if __name__ == '__main__': unittest.main()
