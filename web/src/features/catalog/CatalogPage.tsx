import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createCatalogProduct,
  getCatalogCategories,
  getCatalogSummary,
  listCatalog,
  updateCatalogProduct,
  type CatalogProductInput,
} from '../../api/catalog'
import type { CatalogPriceTier, CatalogProduct } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

function emptyTier(): Omit<CatalogPriceTier,'id'> {
  return {min_qty:0,max_qty:null,price:0,price_unit:1,is_default:true,sort_order:0}
}

function emptyProduct(): CatalogProductInput {
  return {
    source_item_code:null,
    category:'General',
    name:'',
    unit:'ea',
    currency:'USD',
    manual_price:false,
    active:true,
    tiers:[emptyTier()],
  }
}

function pricingLabel(product:CatalogProduct){
  if(product.manual_price)return 'Manual price'
  if(!product.tiers.length)return 'No price'
  if(product.tiers.length===1){
    const tier=product.tiers[0]
    return '$'+(Number(tier.price)/(Number(tier.price_unit)||1)).toFixed(2)
  }
  const prices=product.tiers.map(tier=>Number(tier.price)/(Number(tier.price_unit)||1))
  return '$'+Math.min(...prices).toFixed(2)+'–$'+Math.max(...prices).toFixed(2)+' · '+product.tiers.length+' tiers'
}

export function CatalogPage(){
  const {session}=useSession()
  const {online}=useOnline()
  const qc=useQueryClient()
  const canManage=session?.employee.role==='supervisor'||session?.employee.role==='admin'
  const [search,setSearch]=useState('')
  const [category,setCategory]=useState('')
  const [showInactive,setShowInactive]=useState(false)
  const [editing,setEditing]=useState<CatalogProduct|null>(null)
  const [formOpen,setFormOpen]=useState(false)
  const [form,setForm]=useState<CatalogProductInput>(emptyProduct)

  const catalog=useQuery({
    queryKey:['catalog-page',search,category,showInactive],
    queryFn:()=>listCatalog({search,category,include_inactive:showInactive,limit:2000}),
    enabled:online,
  })
  const categories=useQuery({queryKey:['catalog-categories'],queryFn:getCatalogCategories,enabled:online})
  const summary=useQuery({queryKey:['catalog-summary'],queryFn:getCatalogSummary,enabled:online})

  async function refresh(){
    await Promise.all([
      qc.invalidateQueries({queryKey:['catalog-page']}),
      qc.invalidateQueries({queryKey:['catalog-all']}),
      qc.invalidateQueries({queryKey:['catalog-categories']}),
      qc.invalidateQueries({queryKey:['catalog-summary']}),
    ])
  }

  const save=useMutation({
    mutationFn:()=>editing?updateCatalogProduct(editing,form):createCatalogProduct(form),
    onSuccess:async()=>{
      setEditing(null);setFormOpen(false);setForm(emptyProduct());await refresh()
    },
  })

  function startNew(){
    setEditing(null);setForm(emptyProduct());setFormOpen(true)
  }

  function startEdit(product:CatalogProduct){
    setEditing(product)
    setForm({
      source_item_code:product.source_item_code,
      category:product.category,
      name:product.name,
      unit:product.unit,
      currency:product.currency,
      manual_price:product.manual_price,
      active:product.active,
      tiers:product.tiers.map(tier=>({min_qty:tier.min_qty,max_qty:tier.max_qty,price:tier.price,price_unit:tier.price_unit,is_default:tier.is_default,sort_order:tier.sort_order})),
    })
    setFormOpen(true)
  }

  function changeTier(index:number,patch:Partial<Omit<CatalogPriceTier,'id'>>){
    setForm(old=>({...old,tiers:old.tiers.map((tier,i)=>i===index?{...tier,...patch}:tier)}))
  }

  function addTier(){
    setForm(old=>({...old,manual_price:false,tiers:[
      ...old.tiers.map(tier=>({...tier,is_default:false})),
      {min_qty:1,max_qty:null,price:0,price_unit:1,is_default:false,sort_order:old.tiers.length},
    ]}))
  }

  function removeTier(index:number){
    setForm(old=>({...old,tiers:old.tiers.filter((_,i)=>i!==index).map((tier,i)=>({...tier,sort_order:i}))}))
  }

  const categoryOptions=useMemo(()=>categories.data?.categories??[],[categories.data?.categories])

  return <section>
    <div className="page-heading">
      <div><h1>Products & Pricing</h1><p className="muted">Shared product catalog used by Work Orders and Inventory.</p></div>
      {online&&canManage&&<button onClick={formOpen?()=>{setFormOpen(false);setEditing(null)}:startNew}>{formOpen?'Close':'New Product'}</button>}
    </div>

    {!online&&<div className="offline-banner">Products & Pricing requires an online connection.</div>}

    {summary.data&&<div className="metric-grid">
      <div className="metric"><span>Active products</span><strong>{summary.data.active_products}</strong></div>
      <div className="metric"><span>Categories</span><strong>{summary.data.categories}</strong></div>
      <div className="metric"><span>Tiered pricing</span><strong>{summary.data.tiered_products}</strong></div>
      <div className="metric"><span>Manual price</span><strong>{summary.data.manual_price}</strong></div>
    </div>}

    {summary.data?.initial_import&&<div className="panel catalog-import-note">
      <strong>Initial price list loaded</strong>
      <span>{summary.data.initial_import.source_name} · {summary.data.initial_import.product_count} products · {summary.data.initial_import.price_row_count} unique price rows</span>
    </div>}

    {formOpen&&canManage&&<form className="panel form-grid" onSubmit={event=>{event.preventDefault();save.mutate()}}>
      <div className="span-2 section-heading"><h2>{editing?'Edit Product':'New Product'}</h2>{editing&&<span>Version {editing.version}</span>}</div>
      <label>Item code<input maxLength={100} value={form.source_item_code??''} onChange={event=>setForm(old=>({...old,source_item_code:event.target.value||null}))}/></label>
      <label>Category<input list="catalog-category-list" required maxLength={120} value={form.category} onChange={event=>setForm(old=>({...old,category:event.target.value}))}/><datalist id="catalog-category-list">{categoryOptions.map(value=><option key={value} value={value}/>)}</datalist></label>
      <label className="span-2">Product name<input required maxLength={220} value={form.name} onChange={event=>setForm(old=>({...old,name:event.target.value}))}/></label>
      <label>Unit<input required maxLength={40} value={form.unit} onChange={event=>setForm(old=>({...old,unit:event.target.value}))}/></label>
      <label>Currency<input required maxLength={3} value={form.currency} onChange={event=>setForm(old=>({...old,currency:event.target.value.toUpperCase()}))}/></label>
      <label className="checkbox"><input type="checkbox" checked={form.manual_price} onChange={event=>setForm(old=>({...old,manual_price:event.target.checked,tiers:event.target.checked?[]:(old.tiers.length?old.tiers:[emptyTier()])}))}/>Manual price / enter price on Work Order</label>
      <label className="checkbox"><input type="checkbox" checked={form.active} onChange={event=>setForm(old=>({...old,active:event.target.checked}))}/>Active product</label>

      {!form.manual_price&&<div className="span-2 catalog-tier-editor">
        <div className="section-heading"><div><h3>Price Tiers</h3><p className="muted">Use 0–0 as a default price, or quantity ranges for volume pricing.</p></div><button type="button" className="secondary" onClick={addTier}>Add Tier</button></div>
        {form.tiers.map((tier,index)=><div className="catalog-tier-row" key={index}>
          <label>From<input type="number" min="0" step="0.01" value={tier.min_qty} onChange={event=>changeTier(index,{min_qty:Number(event.target.value)||0})}/></label>
          <label>To<input type="number" min="0" step="0.01" value={tier.max_qty??''} placeholder="No max" onChange={event=>changeTier(index,{max_qty:event.target.value===''?null:Number(event.target.value)})}/></label>
          <label>Price<input type="number" min="0" step="0.0001" value={tier.price} onChange={event=>changeTier(index,{price:Number(event.target.value)||0})}/></label>
          <label>Price unit<input type="number" min="0.0001" step="0.0001" value={tier.price_unit} onChange={event=>changeTier(index,{price_unit:Number(event.target.value)||1})}/></label>
          <label className="checkbox"><input type="checkbox" checked={tier.is_default} onChange={event=>{
            const checked=event.target.checked
            setForm(old=>({...old,tiers:old.tiers.map((row,i)=>({...row,is_default:i===index?checked:(checked?false:row.is_default)}))}))
          }}/>Default</label>
          <button type="button" className="danger-link" onClick={()=>removeTier(index)} disabled={form.tiers.length<=1}>Remove</button>
        </div>)}
      </div>}

      {save.error&&<p className="error span-2">{save.error instanceof Error?save.error.message:'Unable to save product'}</p>}
      <div className="form-actions span-2"><button disabled={save.isPending}>{save.isPending?'Saving…':editing?'Save Product':'Create Product'}</button><button type="button" className="secondary" onClick={()=>{setFormOpen(false);setEditing(null)}}>Cancel</button></div>
    </form>}

    <div className="toolbar order-filters">
      <input placeholder="Search item code, product, or category…" value={search} onChange={event=>setSearch(event.target.value)}/>
      <select aria-label="Catalog category filter" value={category} onChange={event=>setCategory(event.target.value)}><option value="">All categories</option>{categoryOptions.map(value=><option key={value}>{value}</option>)}</select>
      {canManage&&<label className="checkbox"><input type="checkbox" checked={showInactive} onChange={event=>setShowInactive(event.target.checked)}/>Show inactive</label>}
    </div>

    <div className="panel">
      <div className="section-heading"><h2>Catalog</h2><span>{catalog.data?.total??0} matching</span></div>
      {catalog.isLoading?<p>Loading catalog…</p>:catalog.error?<p className="error">{catalog.error instanceof Error?catalog.error.message:'Unable to load catalog'}</p>:catalog.data?.products.length?<div className="table-wrap"><table>
        <thead><tr><th>Item</th><th>Product</th><th>Category</th><th>Unit</th><th>Pricing</th><th>Status</th>{canManage&&<th></th>}</tr></thead>
        <tbody>{catalog.data.products.map(product=><tr key={product.id} className={product.active?undefined:'inactive-row'}>
          <td>{product.source_item_code||'—'}</td><td><strong>{product.name}</strong></td><td>{product.category}</td><td>{product.unit}</td><td>{pricingLabel(product)}</td><td>{product.active?'Active':'Inactive'}</td>
          {canManage&&<td><button className="small-button secondary" onClick={()=>startEdit(product)}>Edit</button></td>}
        </tr>)}</tbody>
      </table></div>:<p className="empty-state">No products match these filters.</p>}
    </div>
  </section>
}
