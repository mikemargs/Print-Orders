import { apiFetch } from './http'
import type { CatalogPriceTier, CatalogProduct, CatalogSummary } from './types'

export type CatalogProductInput = {
  source_item_code: string | null
  category: string
  name: string
  unit: string
  currency: string
  manual_price: boolean
  active: boolean
  tiers: Omit<CatalogPriceTier,'id'>[]
}

export const listCatalog = (options: {
  search?: string
  category?: string
  include_inactive?: boolean
  quantity?: number
  limit?: number
  offset?: number
} = {}) => {
  const params = new URLSearchParams()
  Object.entries(options).forEach(([key,value]) => {
    if (value !== undefined && value !== '' && value !== false) params.set(key,String(value))
  })
  return apiFetch<{products:CatalogProduct[];total:number}>(`/api/catalog?${params}`)
}

export const getCatalogSummary = () => apiFetch<CatalogSummary>('/api/catalog/summary')
export const getCatalogCategories = () => apiFetch<{categories:string[]}>('/api/catalog/categories')

export const createCatalogProduct = (input: CatalogProductInput) =>
  apiFetch<CatalogProduct>('/api/catalog',{method:'POST',body:JSON.stringify(input)})

export const updateCatalogProduct = (product: CatalogProduct,input: CatalogProductInput) =>
  apiFetch<CatalogProduct>(`/api/catalog/${product.id}`,{
    method:'PATCH',
    body:JSON.stringify({...input,version:product.version}),
  })

export function resolveCatalogPrice(product: CatalogProduct, quantity: number): number | null {
  if (product.manual_price) return null
  const q=Math.max(Number(quantity)||0,0)
  const ranged=product.tiers.filter(tier =>
    !tier.is_default &&
    q >= Number(tier.min_qty) &&
    (tier.max_qty == null || q <= Number(tier.max_qty)),
  )
  const chosen=ranged.sort((a,b)=>Number(b.min_qty)-Number(a.min_qty)||b.sort_order-a.sort_order)[0]
    ?? product.tiers.find(tier=>tier.is_default)
    ?? [...product.tiers].sort((a,b)=>Number(a.min_qty)-Number(b.min_qty)||a.sort_order-b.sort_order)[0]
  if(!chosen)return null
  const priceUnit=Number(chosen.price_unit)||1
  return Number(chosen.price)/priceUnit
}

export function catalogDisplayLabel(product: CatalogProduct): string {
  const code=product.source_item_code ? product.source_item_code+' · ' : ''
  return code+product.name+' · '+product.category
}
