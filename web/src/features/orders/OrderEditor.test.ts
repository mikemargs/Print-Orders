import { describe, expect, it } from 'vitest'
import type { CatalogProduct, WorkOrder } from '../../api/types'
import { manualPricesConfirmed, toOrderFormValues } from './OrderEditor'

describe('toOrderFormValues', () => {
  it('strips server-managed fields before an order is submitted', () => {
    const order: WorkOrder = {
      id: 'order-1',
      version: 4,
      customer_id: 'customer-1',
      location_id: 'location-1',
      order_number: '1004',
      status: 'In Production',
      priority: 'High',
      received_date: '2026-10-03',
      due_date: '2026-10-07',
      assigned_to: 'Nick',
      delivery_method: 'Pickup',
      po_number: 'PO-1',
      description: 'Test order',
      artwork_path: '',
      production_notes: 'Print carefully',
      customer_notes: '',
      tax_rate: 8.625,
      deposit: 10,
      paid_in_full: false,
      discount: 4.79,
      discount_mode: 'percent',
      discount_percent: 10,
      subtotal: 47.9,
      total: 52.03,
      balance: 42.03,
      items: [{ item_name: 'Poster', quantity: 1, unit_price: 47.9, server_only: 'drop-me' }],
      updated_at: '2026-10-03T23:53:51.700690+00:00',
      updated_by: 'employee-1',
      is_deleted: false,
    }

    const payload = toOrderFormValues(order)

    expect(payload).toEqual({
      customer_id: 'customer-1',
      location_id: 'location-1',
      status: 'In Production',
      priority: 'High',
      received_date: '2026-10-03',
      due_date: '2026-10-07',
      assigned_to: 'Nick',
      delivery_method: 'Pickup',
      po_number: 'PO-1',
      description: 'Test order',
      production_notes: 'Print carefully',
      customer_notes: '',
      tax_rate: 8.625,
      deposit: 10,
      paid_in_full: false,
      discount: 4.79,
      discount_mode: 'percent',
      discount_percent: 10,
      items: [{
        item_name: 'Poster',
        quantity: 1,
        unit_price: 47.9,
        catalog_product_id: '',
        catalog_item_code: '',
        catalog_category: '',
        catalog_unit: '',
        price_overridden: false,
      }],
    })
    expect(payload).not.toHaveProperty('id')
    expect(payload).not.toHaveProperty('subtotal')
    expect(payload).not.toHaveProperty('total')
    expect(payload).not.toHaveProperty('balance')
    expect(payload).not.toHaveProperty('updated_at')
    expect(payload).not.toHaveProperty('updated_by')
    expect(payload).not.toHaveProperty('is_deleted')
  })
})

it('preserves reordered historical manual prices without exempting new duplicate rows',()=>{
 const products=[{id:'manual',manual_price:true}] as CatalogProduct[]
 const item={catalog_product_id:'manual',quantity:1,unit_price:0,price_overridden:false}
 expect(manualPricesConfirmed([item],products,[{item_name:'Custom',quantity:1,unit_price:5},item])).toBe(true)
 expect(manualPricesConfirmed([item,item],products,[item])).toBe(false)
 expect(manualPricesConfirmed([{...item,price_overridden:true},item],products,[item])).toBe(false)
})
