import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../../api/http'
import type { Customer, WorkOrder } from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
import { cacheCustomers, cacheOrders, cachedCustomer, cachedOrder } from '../../offline/db'

export function WorkTicket(){
  const {id}=useParams();const {session}=useSession();const {online}=useOnline()
  const order=useQuery({queryKey:['ticket-order',id,online],queryFn:async()=>{if(!id)throw new Error('Order missing');if(!online){const cached=await cachedOrder(id);if(!cached)throw new Error('Order is not cached on this device');return cached}const data=await apiFetch<WorkOrder>(`/api/orders/${id}`);await cacheOrders([data]);return data},enabled:Boolean(id)})
  const customer=useQuery({queryKey:['ticket-customer',order.data?.customer_id,online],queryFn:async()=>{const customerId=order.data!.customer_id;if(!online)return cachedCustomer(customerId);const data=await apiFetch<Customer>(`/api/customers/${customerId}`);await cacheCustomers([data]);return data},enabled:Boolean(order.data?.customer_id)})
  if(order.error)return <p className="error">{order.error instanceof Error?order.error.message:'Unable to load work order'}</p>
  if(!order.data)return <p>Loading…</p>
  const o=order.data,c=customer.data;const location=session?.locations?.find(x=>x.id===o.location_id)||session?.location
  return <article className="work-ticket"><div className="print-actions"><button onClick={()=>window.print()}>Print</button></div>{!online&&<div className="notice">Printing cached offline copy.</div>}<header><h1>Work Order {o.order_number}</h1><p>{location?.name} #{location?.store_number}</p></header><div className="ticket-grid"><section><h2>Customer</h2><p><strong>{c?.company||`${c?.first_name??''} ${c?.last_name??''}`.trim()||'Customer'}</strong><br/>{c?.phone}<br/>{c?.email}</p></section><section><h2>Production</h2><p>Status: <strong>{o.status}</strong><br/>Priority: <strong>{o.priority}</strong><br/>Received: {o.received_date}<br/>Due: {o.due_date||'—'}<br/>Assigned: {o.assigned_to||'—'}</p></section></div><h2>{o.description||'Order Items'}</h2><table><thead><tr><th>Item</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead><tbody>{o.items.map((x,i)=><tr key={i}><td>{String(x.item_name??x.description??'Item')}</td><td>{x.quantity}</td><td>${Number(x.unit_price).toFixed(2)}</td><td>${(Number(x.quantity)*Number(x.unit_price)).toFixed(2)}</td></tr>)}</tbody></table><div className="ticket-totals"><p>Subtotal ${Number(o.subtotal).toFixed(2)}</p><p>Discount{o.discount_mode==='percent'?' ('+Number(o.discount_percent).toFixed(2)+'%)':''} -${Number(o.discount).toFixed(2)}</p><p>Total <strong>${Number(o.total).toFixed(2)}</strong></p><p>Deposit -${Number(o.deposit).toFixed(2)}</p><p>Balance <strong>${Number(o.balance).toFixed(2)}</strong></p></div>{o.production_notes&&<section><h2>Production notes</h2><p className="prewrap">{o.production_notes}</p></section>}{o.customer_notes&&<section><h2>Customer notes</h2><p className="prewrap">{o.customer_notes}</p></section>}</article>
}
