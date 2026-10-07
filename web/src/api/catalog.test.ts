import { describe, expect, it } from 'vitest'
import { resolveCatalogPrice } from './catalog'
import type { CatalogProduct } from './types'

function product(overrides: Partial<CatalogProduct> = {}): CatalogProduct {
  return {
    id: 'p1',
    source_item_code: '36001',
    category: 'Copies',
    name: '8.5x11 Copies',
    unit: 'ea',
    currency: 'USD',
    manual_price: false,
    active: true,
    version: 1,
    created_by: 'seed',
    updated_by: 'seed',
    created_at: '',
    updated_at: '',
    resolved_price: 0.3,
    resolved_tier_id: null,
    tiers: [
      { min_qty: 1, max_qty: 100, price: 0.30, price_unit: 1, is_default: false, sort_order: 0 },
      { min_qty: 100, max_qty: 500, price: 0.25, price_unit: 1, is_default: false, sort_order: 1 },
      { min_qty: 500, max_qty: 1000, price: 0.15, price_unit: 1, is_default: false, sort_order: 2 },
      { min_qty: 1000, max_qty: null, price: 0.08, price_unit: 1, is_default: false, sort_order: 3 },
    ],
    ...overrides,
  }
}

describe('resolveCatalogPrice', () => {
  it('uses the highest applicable quantity tier at shared boundaries', () => {
    const item = product()
    expect(resolveCatalogPrice(item, 1)).toBeCloseTo(0.30)
    expect(resolveCatalogPrice(item, 100)).toBeCloseTo(0.25)
    expect(resolveCatalogPrice(item, 500)).toBeCloseTo(0.15)
    expect(resolveCatalogPrice(item, 1000)).toBeCloseTo(0.08)
  })

  it('uses a default tier when no ranged tier matches', () => {
    const item = product({
      tiers: [
        { min_qty: 0, max_qty: null, price: 12, price_unit: 1, is_default: true, sort_order: 0 },
        { min_qty: 10, max_qty: 20, price: 8, price_unit: 1, is_default: false, sort_order: 1 },
      ],
    })
    expect(resolveCatalogPrice(item, 2)).toBeCloseTo(12)
    expect(resolveCatalogPrice(item, 12)).toBeCloseTo(8)
  })

  it('returns null for manual-price catalog products', () => {
    expect(resolveCatalogPrice(product({ manual_price: true }), 10)).toBeNull()
  })

  it('honors price units', () => {
    const item = product({
      tiers: [
        { min_qty: 0, max_qty: null, price: 25, price_unit: 100, is_default: true, sort_order: 0 },
      ],
    })
    expect(resolveCatalogPrice(item, 50)).toBeCloseTo(0.25)
  })
})
