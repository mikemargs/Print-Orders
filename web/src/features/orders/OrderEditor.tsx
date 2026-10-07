import { useEffect, useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, apiFetch } from '../../api/http'
import { listCatalog, resolveCatalogPrice } from '../../api/catalog'
import type { CatalogProduct, Customer, LineItem, WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheCustomers, cachedCustomers, cacheOrders, cachedOrder } from '../../offline/db'
import { CatalogProductPicker } from '../catalog/CatalogProductPicker'
import { AttachmentPanel } from '../files/AttachmentPanel'

type DiscountMode = 'amount' | 'percent'
type FormValues = {customer_id:string; location_id:string; status:string; priority:string; received_date:string; due_date:string; assigned_to:string; delivery_method:string; po_number:string; description:string; production_notes:string; customer_notes:string; tax_rate:number; deposit:number; discount:number; discount_mode:DiscountMode; discount_percent:number; items:LineItem[]}
const today=()=>new Date().toISOString().slice(0,10)

export function toOrderFormValues(source: Partial<FormValues>): FormValues {
  return {
    customer_id: source.customer_id ?? '',
    location_id: source.location_id ?? '',
    status: source.status ?? 'New',
    priority: source.priority ?? 'Normal',
    received_date: source.received_date ?? today(),
    due_date: source.due_date ?? '',
    assigned_to: source.assigned_to ?? '',
    delivery_method: source.delivery_method ?? 'Pickup',
    po_number: source.po_number ?? '',
    description: source.description ?? '',
    production_notes: source.production_notes ?? '',
    customer_notes: source.customer_notes ?? '',
    tax_rate: Number(source.tax_rate) || 0,
    deposit: Number(source.deposit) || 0,
    discount: Number(source.discount) || 0,
    discount_mode: source.discount_mode === 'percent' ? 'percent' : 'amount',
    discount_percent: Number(source.discount_percent) || 0,
    items: (source.items ?? [{item_name:'',quantity:1,unit_price:0}]).map(item => ({
      item_name: String(item.item_name ?? item.description ?? ''),
      quantity: Number(item.quantity) || 0,
      unit_price: Number(item.unit_price) || 0,
      catalog_product_id: typeof item.catalog_product_id === 'string' ? item.catalog_product_id : '',
      catalog_item_code: typeof item.catalog_item_code === 'string' ? item.catalog_item_code : '',
      catalog_category: typeof item.catalog_category === 'string' ? item.catalog_category : '',
      catalog_unit: typeof item.catalog_unit === 'string' ? item.catalog_unit : '',
      price_overridden: item.price_overridden === true,
    })),
  }
}

export function OrderEditor() {
  const {id}=useParams(); const editing=Boolean(id&&id!=='new'); const [searchParams]=useSearchParams(); const initialCustomerId=!editing?(searchParams.get('customer_id')??''):''; const navigate=useNavigate(); const queryClient=useQueryClient(); const {session}=useSession(); const {online}=useOnline(); const [version,setVersion]=useState(0); const [error,setError]=useState(''); const [conflict,setConflict]=useState<WorkOrder|null>(null); const [offlineOrder,setOfflineOrder]=useState<WorkOrder|null>(null); const [currentOrder,setCurrentOrder]=useState<WorkOrder|null>(null); const [editMode,setEditMode]=useState(!editing); const [deleting,setDeleting]=useState(false)
  const [customerRows,setCustomers]=useState<Customer[]>([])
  const {register,control,handleSubmit,reset,watch,setValue,getValues,formState:{isSubmitting}}=useForm<FormValues>({defaultValues:{customer_id:initialCustomerId,location_id:session?.location.id??'',status:'New',priority:'Normal',received_date:today(),due_date:'',assigned_to:'',delivery_method:'Pickup',po_number:'',description:'',production_notes:'',customer_notes:'',tax_rate:0,deposit:0,discount:0,discount_mode:'amount',discount_percent:0,items:[{item_name:'',quantity:1,unit_price:0}]}})
  const fields=useFieldArray({control,name:'items'})
  const catalog=useQuery({queryKey:['catalog-all'],queryFn:()=>listCatalog({limit:2000}),enabled:online})
  useEffect(()=>{if(!editing){setEditMode(true);setCurrentOrder(null)}else setEditMode(false);if(!online){if(editing&&id)void cachedOrder(id).then(x=>setOfflineOrder(x??null));return}void cachedCustomers().then(rows=>{if(rows.length)setCustomers(rows)});void apiFetch<{customers:Customer[]}>('/api/customers?limit=200').then(async x=>{setCustomers(x.customers);await cacheCustomers(x.customers)});if(editing)void apiFetch<WorkOrder>(`/api/orders/${id}`).then(async o=>{setCurrentOrder(o);setVersion(o.version);reset(toOrderFormValues(o));await cacheOrders([o])}).catch(e=>setError(e instanceof Error?e.message:'Unable to load order'))},[editing,id,reset,online])
  const catalogProducts=catalog.data?.products??[]
  function catalogProductFor(index:number){const id=getValues(`items.${index}.catalog_product_id`);return catalogProducts.find(product=>product.id===id)??null}
  function applyCatalogProduct(index:number,product:CatalogProduct|null){
    if(!product){
      setValue(`items.${index}.catalog_product_id`,'')
      setValue(`items.${index}.catalog_item_code`,'')
      setValue(`items.${index}.catalog_category`,'')
      setValue(`items.${index}.catalog_unit`,'')
      return
    }
    const quantity=Number(getValues(`items.${index}.quantity`))||1
    const price=resolveCatalogPrice(product,quantity)
    setValue(`items.${index}.catalog_product_id`,product.id)
    setValue(`items.${index}.catalog_item_code`,product.source_item_code??'')
    setValue(`items.${index}.catalog_category`,product.category)
    setValue(`items.${index}.catalog_unit`,product.unit)
    setValue(`items.${index}.item_name`,product.name)
    setValue(`items.${index}.price_overridden`,false)
    setValue(`items.${index}.unit_price`,price??0)
  }
  function refreshCatalogPrice(index:number,quantity:number){
    const product=catalogProductFor(index)
    if(!product||getValues(`items.${index}.price_overridden`))return
    const price=resolveCatalogPrice(product,quantity)
    if(price!=null)setValue(`items.${index}.unit_price`,price)
  }
  function restoreCatalogPrice(index:number){
    const product=catalogProductFor(index)
    if(!product)return
    const price=resolveCatalogPrice(product,Number(getValues(`items.${index}.quantity`))||1)
    if(price==null)return
    setValue(`items.${index}.unit_price`,price)
    setValue(`items.${index}.price_overridden`,false)
  }
  const items=watch('items'); const discountMode=watch('discount_mode'); const discountPercent=watch('discount_percent'); const discountAmount=watch('discount'); const subtotal=(items??[]).reduce((sum,x)=>sum+(Number(x.quantity)||0)*(Number(x.unit_price)||0),0); const previewDiscount=discountMode==='percent'?subtotal*Math.min(Math.max(Number(discountPercent)||0,0),100)/100:Math.max(Number(discountAmount)||0,0)
  const submit=handleSubmit(async values=>{setError('');setConflict(null);try{const payload=toOrderFormValues(values);const saved=editing?await apiFetch<WorkOrder>(`/api/orders/${id}`,{method:'PATCH',body:JSON.stringify({...payload,version})}):await apiFetch<WorkOrder>('/api/orders',{method:'POST',body:JSON.stringify(payload)});await cacheOrders([saved]);await queryClient.invalidateQueries({queryKey:['orders']});if(editing){setCurrentOrder(saved);setVersion(saved.version);reset(toOrderFormValues(saved));setEditMode(false)}else navigate(`/orders/${saved.id}`)}catch(e){if(e instanceof ApiError&&e.status===409){setConflict(e.current as WorkOrder);setError('This work order changed on another device. Review the current server version before trying again.')}else setError(e instanceof Error?e.message:'Save failed')}})
  async function remove(){if(!editing||!id||!window.confirm('Delete this work order?'))return;setDeleting(true);setError('');try{await apiFetch(`/api/orders/${id}`,{method:'DELETE',body:JSON.stringify({version})});await queryClient.invalidateQueries({queryKey:['orders']});navigate('/orders')}catch(e){setError(e instanceof Error?e.message:'Delete failed')}finally{setDeleting(false)}}
  if(!online){if(!editing)return <section><div className="page-heading"><h1>New work order</h1></div><div className="panel muted">Creating work orders is unavailable offline.</div></section>;if(!offlineOrder)return <section><div className="page-heading"><h1>Work order</h1></div><div className="panel muted">This order is not available in the local cache.</div></section>;const o=offlineOrder;return <section><div className="page-heading"><div><h1>{o.order_number}</h1><p className="muted">Cached read-only copy</p></div><Link className="button secondary" to="/orders">Back</Link></div><div className="panel detail-grid"><div><span>Status</span><strong>{o.status}</strong></div><div><span>Priority</span><strong>{o.priority}</strong></div><div><span>Due</span><strong>{o.due_date||'—'}</strong></div><div><span>Total / Balance</span><strong>${o.total.toFixed(2)} / ${o.balance.toFixed(2)}</strong></div><div className="span-2"><span>Description</span><strong>{o.description||'—'}</strong></div></div><div className="panel table-wrap"><table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th></tr></thead><tbody>{o.items.map((x,i)=><tr key={i}><td>{String(x.item_name??x.description??'Item')}</td><td>{x.quantity}</td><td>${Number(x.unit_price).toFixed(2)}</td></tr>)}</tbody></table></div></section>}
  if(editing&&!currentOrder)return <section><div className="page-heading"><h1>Work order</h1></div>{error?<p className="error">{error}</p>:<p>Loading…</p>}</section>
  if(editing&&!editMode&&currentOrder){const o=currentOrder;const customer=customerRows.find(row=>row.id===o.customer_id);const location=session?.locations.find(row=>row.id===o.location_id);const taxAmount=Math.max(Number(o.subtotal)-Number(o.discount),0)*(Number(o.tax_rate)/100);return <section className="read-only-order">
    <div className="page-heading"><div><h1>{o.order_number}</h1><p className="muted">Work order details</p></div><div className="button-row"><button type="button" onClick={()=>setEditMode(true)}>Edit Work Order</button><Link className="button secondary" to={`/orders/${id}/print`}>Print ticket</Link><Link className="button secondary" to="/orders">Back</Link></div></div>
    <div className="panel detail-grid">
      <div><span>Customer</span><strong>{customer?.company||`${customer?.first_name??''} ${customer?.last_name??''}`.trim()||'Customer'}</strong></div>
      <div><span>Store</span><strong>{location?`${location.name} #${location.store_number}`:'—'}</strong></div>
      <div><span>Status</span><strong>{o.status}</strong></div><div><span>Priority</span><strong>{o.priority}</strong></div>
      <div><span>Received</span><strong>{o.received_date||'—'}</strong></div><div><span>Due</span><strong>{o.due_date||'—'}</strong></div>
      <div><span>Assigned to</span><strong>{o.assigned_to||'—'}</strong></div><div><span>Delivery</span><strong>{o.delivery_method||'—'}</strong></div>
      <div><span>PO number</span><strong>{o.po_number||'—'}</strong></div><div className="span-2"><span>Description</span><strong>{o.description||'—'}</strong></div>
    </div>
    <div className="panel table-wrap"><div className="section-heading"><h2>Line items</h2></div><table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead><tbody>{o.items.map((x,i)=><tr key={i}><td>{String(x.item_name??x.description??'Item')}</td><td>{x.quantity}</td><td>${Number(x.unit_price).toFixed(2)}</td><td>${(Number(x.quantity)*Number(x.unit_price)).toFixed(2)}</td></tr>)}</tbody></table></div>
    <div className="panel ticket-totals"><p>Subtotal ${Number(o.subtotal).toFixed(2)}</p><p>Tax ${taxAmount.toFixed(2)}</p><p>Discount{o.discount_mode==='percent'?` (${Number(o.discount_percent).toFixed(2)}%)`:''} -${Number(o.discount).toFixed(2)}</p><p>Total <strong>${Number(o.total).toFixed(2)}</strong></p><p>Deposit -${Number(o.deposit).toFixed(2)}</p><p>Balance <strong>${Number(o.balance).toFixed(2)}</strong></p></div>
    {o.production_notes&&<div className="panel"><h2>Production notes</h2><p className="prewrap">{o.production_notes}</p></div>}
    {o.customer_notes&&<div className="panel"><h2>Customer notes</h2><p className="prewrap">{o.customer_notes}</p></div>}
  </section>}
  return <section><div className="page-heading"><div><h1>{editing?'Edit work order':'New work order'}</h1>{editing&&<p className="muted">{currentOrder?.order_number} · Version {version}</p>}</div>{editing&&<div className="button-row"><Link className="button secondary" to={`/orders/${id}/print`}>Print ticket</Link>{(session?.employee.role==='supervisor'||session?.employee.role==='admin')&&<button type="button" className="danger" onClick={()=>void remove()} disabled={deleting}>{deleting?'Deleting…':'Delete work order'}</button>}</div>}</div>
    {conflict&&<div className="conflict-banner"><strong>Server version {conflict.version}</strong><span>Status: {conflict.status}; due {conflict.due_date||'not set'}.</span><button onClick={()=>{setVersion(conflict.version);reset(toOrderFormValues(conflict));setConflict(null);setError('')}}>Load server version</button></div>}
    <form onSubmit={submit} className="form-stack"><div className="panel form-grid"><label>Customer<select {...register('customer_id',{required:true})}><option value="">Choose customer…</option>{customerRows.map(c=><option key={c.id} value={c.id}>{c.company||`${c.first_name} ${c.last_name}`}</option>)}</select></label><label>Store<select {...register('location_id',{required:true})}>{(session?.employee.role==='admin'?session.locations:[session?.location].filter(Boolean)).map(loc=><option key={loc!.id} value={loc!.id}>{loc!.name} #{loc!.store_number}</option>)}</select></label><label>Status<select {...register('status')} >{['Quote','New','Awaiting Artwork','Proof Sent','Proof Approved','In Production','Ready for Pickup','Completed','On Hold','Cancelled'].map(x=><option key={x}>{x}</option>)}</select></label><label>Priority<select {...register('priority')}><option>Normal</option><option>High</option><option>Rush</option></select></label><label>Received<input type="date" {...register('received_date')} /></label><label>Due<input type="date" {...register('due_date')} /></label><label>Assigned to<input {...register('assigned_to')} /></label><label>Delivery<select {...register('delivery_method')}><option>Pickup</option><option>Delivery</option><option>Ship</option></select></label><label>PO number<input {...register('po_number')} /></label><label className="span-2">Description<input {...register('description')} /></label></div>
      <div className="panel"><div className="section-heading"><div><h2>Line items</h2><p className="muted">Choose a catalog product for automatic pricing, or enter a custom item.</p></div><button type="button" className="secondary" onClick={()=>fields.append({item_name:'',quantity:1,unit_price:0,catalog_product_id:'',catalog_item_code:'',catalog_category:'',catalog_unit:'',price_overridden:false})}>Add item</button></div>{fields.fields.map((field,index)=>{const row=items?.[index];const product=row?.catalog_product_id?catalogProducts.find(x=>x.id===row.catalog_product_id):null;return <div className="line-item catalog-line-item" key={field.id}><CatalogProductPicker products={catalogProducts} value={typeof row?.catalog_product_id==='string'?row.catalog_product_id:null} onSelect={product=>applyCatalogProduct(index,product)} idPrefix={'order-catalog-'+index}/><input placeholder="Item / service / custom description" {...register(`items.${index}.item_name` as const)} /><input aria-label="Quantity" min="0" type="number" step="0.01" {...register(`items.${index}.quantity` as const,{valueAsNumber:true,onChange:event=>refreshCatalogPrice(index,Number(event.target.value)||0)})}/><div className="catalog-price-field"><input aria-label="Unit price" min="0" type="number" step="0.0001" {...register(`items.${index}.unit_price` as const,{valueAsNumber:true,onChange:()=>{if(getValues(`items.${index}.catalog_product_id`))setValue(`items.${index}.price_overridden`,true)}})}/>{product?.manual_price&&<small>Manual price item</small>}{row?.price_overridden&&!product?.manual_price&&<button type="button" className="link-button catalog-price-reset" onClick={()=>restoreCatalogPrice(index)}>Use catalog price</button>}</div><button type="button" className="danger-link" onClick={()=>fields.remove(index)}>Remove</button><input type="hidden" {...register(`items.${index}.catalog_product_id` as const)}/><input type="hidden" {...register(`items.${index}.catalog_item_code` as const)}/><input type="hidden" {...register(`items.${index}.catalog_category` as const)}/><input type="hidden" {...register(`items.${index}.catalog_unit` as const)}/><input type="hidden" {...register(`items.${index}.price_overridden` as const)}/></div>})}<p className="totals-preview">Item subtotal preview: <strong>${subtotal.toFixed(2)}</strong> <span className="muted">Catalog prices can be overridden per Work Order. Saved orders keep their historical price.</span></p></div>
      <div className="panel form-grid"><label>Tax %<input min="0" type="number" step="0.0001" {...register('tax_rate',{valueAsNumber:true})}/></label><label>Discount Type<select {...register('discount_mode')}><option value="amount">Dollar Amount ($)</option><option value="percent">Percent (%)</option></select></label>{discountMode==='percent'?<label>Discount %<input min="0" max="100" type="number" step="0.01" {...register('discount_percent',{valueAsNumber:true})}/></label>:<label>Discount Amount ($)<input min="0" type="number" step="0.01" {...register('discount',{valueAsNumber:true})}/></label>}<label>Deposit<input min="0" type="number" step="0.01" {...register('deposit',{valueAsNumber:true})}/></label><div className="discount-preview span-2"><span>Discount preview</span><strong>-${previewDiscount.toFixed(2)}</strong>{discountMode==='percent'&&<small>{Math.min(Math.max(Number(discountPercent)||0,0),100).toFixed(2)}% of ${subtotal.toFixed(2)}</small>}</div><label className="span-2">Production notes<textarea rows={4} {...register('production_notes')}/></label><label className="span-2">Customer notes<textarea rows={3} {...register('customer_notes')}/></label></div>
      {editing&&id&&<AttachmentPanel orderId={id}/>} {error&&<p className="error">{error}</p>}<div className="form-actions"><button disabled={isSubmitting}>{isSubmitting?'Saving…':'Save work order'}</button><button type="button" className="secondary" onClick={()=>{if(editing){reset(toOrderFormValues(currentOrder??{}));setConflict(null);setError('');setEditMode(false)}else navigate('/orders')}}>Cancel</button></div>
    </form></section>
}
