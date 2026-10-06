import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import type { Customer, WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheCustomers, cacheOrders, cachedCustomer, cachedOrder } from '../../offline/db'

const STORE_ADDRESSES: Record<string, string> = {
  '5127': '161 North Main St, Sayville, NY 11782',
  '5345': '1070 Middle Country Rd, Selden, NY 11784',
  '3167': '5507 Nesconset Hwy #10, Mount Sinai, NY 11766',
}

export function storeAddressFor(storeNumber?: string) {
  return storeNumber ? STORE_ADDRESSES[storeNumber] ?? '' : ''
}

export function calculateTaxAmount(subtotal: number, discount: number, taxRate: number) {
  return Math.max(subtotal - discount, 0) * (taxRate / 100)
}

function formatPercent(value: number) {
  return value.toFixed(3).replace(/\.?0+$/, '')
}

export function WorkTicket(){
  const {id}=useParams();const {session}=useSession();const {online}=useOnline()
  const order=useQuery({queryKey:['ticket-order',id,online],queryFn:async()=>{if(!id)throw new Error('Order missing');if(!online){const cached=await cachedOrder(id);if(!cached)throw new Error('Order is not cached on this device');return cached}const data=await apiFetch<WorkOrder>(`/api/orders/${id}`);await cacheOrders([data]);return data},enabled:Boolean(id)})
  const customer=useQuery({queryKey:['ticket-customer',order.data?.customer_id,online],queryFn:async()=>{const customerId=order.data!.customer_id;if(!online)return cachedCustomer(customerId);const data=await apiFetch<Customer>(`/api/customers/${customerId}`);await cacheCustomers([data]);return data},enabled:Boolean(order.data?.customer_id)})
  if(order.error)return <p className="error">{order.error instanceof Error?order.error.message:'Unable to load work order'}</p>
  if(!order.data)return <p>Loading…</p>
  const o=order.data,c=customer.data;const location=session?.locations?.find(x=>x.id===o.location_id)||session?.location
  const storeAddress=storeAddressFor(location?.store_number)
  const taxAmount=calculateTaxAmount(Number(o.subtotal),Number(o.discount),Number(o.tax_rate))
  return <article className="work-ticket">
    <div className="print-actions"><button onClick={()=>window.print()}>Print</button></div>
    {!online&&<div className="notice">Printing cached offline copy.</div>}
    <header className="ticket-header">
      <div className="ticket-brand">
        <div className="ticket-brand-name">THE UPS STORE<sup>®</sup></div>
        <div className="ticket-brand-subtitle">Print &amp; Business Services</div>
        {storeAddress&&<div className="ticket-brand-address">{storeAddress}</div>}
      </div>
      <div className="ticket-order-meta">
        <span>PRINT ORDER</span>
        <strong>{o.order_number}</strong>
        <div>Status: {o.status}</div>
        <div>Priority: {o.priority}</div>
      </div>
    </header>
    <div className="ticket-location">{location?.name||'The UPS Store'}{location?.store_number?` · Store #${location.store_number}`:''}</div>
    <div className="ticket-grid">
      <section><h2 className="ticket-section-title">Customer</h2><p><strong>{c?.company||`${c?.first_name??''} ${c?.last_name??''}`.trim()||'Customer'}</strong><br/>{c?.phone}<br/>{c?.email}</p></section>
      <section><h2 className="ticket-section-title">Production</h2><p>Received: {o.received_date}<br/>Due: {o.due_date||'—'}<br/>Assigned: {o.assigned_to||'—'}</p></section>
    </div>
    <h2 className="ticket-section-title">{o.description||'Order Items'}</h2>
    <table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead><tbody>{o.items.map((x,i)=><tr key={i}><td>{String(x.item_name??x.description??'Item')}</td><td>{x.quantity}</td><td>${Number(x.unit_price).toFixed(2)}</td><td>${(Number(x.quantity)*Number(x.unit_price)).toFixed(2)}</td></tr>)}</tbody></table>
    <div className="ticket-totals"><p>Subtotal ${Number(o.subtotal).toFixed(2)}</p><p>Tax ({formatPercent(Number(o.tax_rate))}%) ${taxAmount.toFixed(2)}</p><p>Discount{o.discount_mode==='percent'?' ('+Number(o.discount_percent).toFixed(2)+'%)':''} -${Number(o.discount).toFixed(2)}</p><p>Total <strong>${Number(o.total).toFixed(2)}</strong></p><p>Deposit -${Number(o.deposit).toFixed(2)}</p><p>Balance <strong>${Number(o.balance).toFixed(2)}</strong></p></div>
    {o.production_notes&&<section><h2 className="ticket-section-title">Production notes</h2><p className="prewrap">{o.production_notes}</p></section>}
    {o.customer_notes&&<section><h2 className="ticket-section-title">Customer notes</h2><p className="prewrap">{o.customer_notes}</p></section>}
    <footer className="ticket-footer"><span>The UPS Store® · {location?.name||'Print Services'}{location?.store_number?` · Store #${location.store_number}`:''}</span><span>Work Order {o.order_number}</span></footer>
  </article>
}
