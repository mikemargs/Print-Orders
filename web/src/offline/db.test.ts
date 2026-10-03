import { beforeEach, describe, expect, it } from 'vitest'
import type { WorkOrder } from '../api/types'
import { cacheOrders, clearOfflineCache, offlineDB } from './db'

const order=(i:number):WorkOrder=>({id:`o-${i}`,version:1,customer_id:'c',location_id:'l',order_number:`WO-${i}`,status:'New',priority:'Normal',received_date:'2026-10-03',due_date:'',assigned_to:'',delivery_method:'Pickup',po_number:'',description:'',artwork_path:'',production_notes:'',customer_notes:'',tax_rate:0,deposit:0,discount:0,subtotal:1,total:1,balance:1,items:[{item_name:'Item',quantity:1,unit_price:1}],updated_at:new Date(2026,0,1,0,0,i%60).toISOString(),updated_by:'e',is_deleted:false})

describe('offline cache',()=>{
  beforeEach(async()=>clearOfflineCache())
  it('bounds cached work orders to the newest 1000 rows',async()=>{
    await cacheOrders(Array.from({length:1005},(_,i)=>order(i)))
    expect(await offlineDB.orders.count()).toBe(1000)
  })
})
