import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../api/http'
import { useOnline } from '../../offline/OnlineState'

export interface OrderDefaults {
  default_tax_rate: number
  default_order_priority: string
  default_delivery_method: string
  version: number
}

export function SettingsPage() {
  const { online } = useOnline()
  const [saved,setSaved] = useState(false)
  const queryClient = useQueryClient()
  const settings = useQuery({queryKey:['settings'], queryFn:()=>apiFetch<OrderDefaults>('/api/settings'), enabled:online,refetchOnWindowFocus:false,refetchOnReconnect:false})
  if (!online) return <p>Settings require an internet connection.</p>
  if (settings.isError) return <div role="alert"><p className="error">Unable to load settings: {settings.error.message}</p><button onClick={()=>void settings.refetch()}>Retry</button></div>
  if (!settings.data || settings.isFetching) return <p>Loading settings…</p>
  return <><SettingsForm key={settings.data.version} settings={settings.data} onEdit={()=>setSaved(false)} onSaved={result=>{
    queryClient.setQueryData(['settings'], result)
    queryClient.setQueryData(['order-defaults'], result)
    setSaved(true)
  }} />{saved&&<p role="status">Settings saved.</p>}</>
}

function SettingsForm({settings,onSaved,onEdit}:{settings:OrderDefaults;onSaved:(settings:OrderDefaults)=>void;onEdit:()=>void}) {
  const { online } = useOnline()
  const [tax,setTax] = useState(String(settings.default_tax_rate))
  const [priority,setPriority] = useState(settings.default_order_priority)
  const [delivery,setDelivery] = useState(settings.default_delivery_method)
  const [saving,setSaving] = useState(false)
  const [error,setError] = useState('')
  async function save(event:React.FormEvent) {
    event.preventDefault(); setError(''); onEdit(); setSaving(true)
    try {
      const result = await apiFetch<OrderDefaults>('/api/settings',{method:'PATCH',body:JSON.stringify({version:settings.version,default_tax_rate:Number(tax),default_order_priority:priority,default_delivery_method:delivery})})
      onSaved(result)
    } catch (e) {setError(e instanceof Error?e.message:'Unable to save settings')}
    finally {setSaving(false)}
  }
  return <section><h1>Settings</h1><p>Company-wide defaults for all stores. Changes apply to new work orders; existing orders keep their saved values. Employees can override defaults on individual orders.</p>
    <form onChange={onEdit} onSubmit={event=>void save(event)}><fieldset disabled={!online||saving} className="panel form-grid">
      <label>Default tax rate (%)<input required type="number" min="0" max="100" step="0.0001" value={tax} onChange={e=>setTax(e.target.value)}/></label>
      <label>Default priority<select value={priority} onChange={e=>setPriority(e.target.value)}>{['Normal','High','Rush'].map(value=><option key={value}>{value}</option>)}</select></label>
      <label>Default delivery method<select value={delivery} onChange={e=>setDelivery(e.target.value)}>{['Pickup','Delivery','Ship'].map(value=><option key={value}>{value}</option>)}</select></label>
      <button type="submit">{saving?'Saving…':'Save settings'}</button>
    </fieldset>{error&&<p role="alert" className="error">{error}</p>}</form></section>
}
