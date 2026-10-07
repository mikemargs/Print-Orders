import { useEffect, useMemo, useState } from 'react'
import type { CatalogProduct } from '../../api/types'
import { catalogDisplayLabel } from '../../api/catalog'

export function CatalogProductPicker({
  products,
  value,
  onSelect,
  disabled=false,
  placeholder='Search products by item code, name, or category…',
  idPrefix='catalog-product',
}:{
  products:CatalogProduct[]
  value?:string|null
  onSelect:(product:CatalogProduct|null)=>void
  disabled?:boolean
  placeholder?:string
  idPrefix?:string
}){
  const selected=products.find(product=>product.id===value)??null
  const [text,setText]=useState(selected?catalogDisplayLabel(selected):'')
  useEffect(()=>{setText(selected?catalogDisplayLabel(selected):'')},[selected])
  const listId=idPrefix+'-list'
  const byLabel=useMemo(()=>{
    const map=new Map<string,CatalogProduct>()
    for(const product of products)map.set(catalogDisplayLabel(product),product)
    return map
  },[products])

  return <div className="catalog-picker">
    <input
      list={listId}
      value={text}
      disabled={disabled}
      placeholder={placeholder}
      aria-label="Catalog product"
      onChange={event=>{
        const next=event.target.value
        setText(next)
        const exact=byLabel.get(next)
        if(exact)onSelect(exact)
        else if(!next)onSelect(null)
      }}
      onBlur={()=>{
        if(!text){onSelect(null);return}
        const exact=byLabel.get(text)
        if(!exact&&selected)setText(catalogDisplayLabel(selected))
      }}
    />
    <datalist id={listId}>
      {products.map(product=><option key={product.id} value={catalogDisplayLabel(product)}/>)}
    </datalist>
    {selected&&<small className="catalog-picker-meta">
      {selected.manual_price?'Manual price':selected.resolved_price==null?'No price set':'$'+selected.resolved_price.toFixed(2)+' at qty 1'}
      {selected.tiers.length>1?' · '+selected.tiers.length+' price tiers':''}
    </small>}
  </div>
}
