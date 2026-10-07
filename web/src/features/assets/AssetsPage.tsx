import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import {
  adjustInventoryItem,
  createInventoryItem,
  getInventoryHistory,
  getInventorySummary,
  listInventory,
  updateInventoryItem,
  type InventoryItemInput,
} from '../../api/inventory'
import {
  addEquipmentService,
  createEquipment,
  equipmentEventTypes,
  equipmentStatuses,
  getEquipmentHistory,
  getEquipmentSummary,
  listEquipment,
  reportEquipmentIssue,
  updateEquipment,
  type EquipmentInput,
} from '../../api/equipment'
import type {
  EquipmentAssetRecord,
  EquipmentServiceEventRecord,
  InventoryItemRecord,
} from '../../api/types'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'

const inventoryReasons = ['Received','Used','Count Correction','Waste','Other'] as const
const today = () => new Date().toISOString().slice(0, 10)

function emptyInventory(locationId: string): InventoryItemInput {
  return {
    location_id: locationId, name: '', sku: '', category: 'General', unit: 'each',
    quantity: 0, reorder_point: 0, target_stock: 0, cost_per_unit: 0,
    vendor: '', vendor_sku: '', notes: '', active: true,
  }
}

function emptyEquipment(locationId: string): EquipmentInput {
  return {
    location_id: locationId, name: '', category: 'Equipment', asset_tag: '',
    manufacturer: '', model: '', serial_number: '', status: 'Operational',
    purchase_date: null, warranty_expiration: null, vendor: '', service_provider: '',
    next_service_date: null, notes: '', active: true,
  }
}

export function AssetsPage() {
  const { session } = useSession()
  const { online } = useOnline()
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState<'inventory' | 'equipment'>(
    searchParams.get('tab') === 'equipment' ? 'equipment' : 'inventory',
  )
  const canManage = session?.employee.role === 'supervisor' || session?.employee.role === 'admin'
  const allowedStores = session?.employee.role === 'admin'
    ? session.locations
    : [session?.location].filter(Boolean)

  const [invSearch, setInvSearch] = useState('')
  const [invLocation, setInvLocation] = useState('')
  const [lowOnly, setLowOnly] = useState(searchParams.get('low') === '1')
  const [showInactive, setShowInactive] = useState(false)
  const [invFormOpen, setInvFormOpen] = useState(false)
  const [editingInv, setEditingInv] = useState<InventoryItemRecord | null>(null)
  const [invForm, setInvForm] = useState<InventoryItemInput>(
    () => emptyInventory(session?.location.id || ''),
  )
  const [adjusting, setAdjusting] = useState<InventoryItemRecord | null>(null)
  const [adjustMode, setAdjustMode] = useState<'add' | 'remove' | 'set'>('add')
  const [adjustQty, setAdjustQty] = useState(0)
  const [adjustReason, setAdjustReason] =
    useState<(typeof inventoryReasons)[number]>('Received')
  const [adjustNotes, setAdjustNotes] = useState('')
  const [invHistoryId, setInvHistoryId] = useState('')

  const [eqSearch, setEqSearch] = useState('')
  const [eqLocation, setEqLocation] = useState('')
  const [eqStatus, setEqStatus] = useState('')
  const [eqAttention, setEqAttention] = useState(searchParams.get('attention') === '1')
  const [includeRetired, setIncludeRetired] = useState(false)
  const [eqFormOpen, setEqFormOpen] = useState(false)
  const [editingEq, setEditingEq] = useState<EquipmentAssetRecord | null>(null)
  const [eqForm, setEqForm] = useState<EquipmentInput>(
    () => emptyEquipment(session?.location.id || ''),
  )
  const [reporting, setReporting] = useState<EquipmentAssetRecord | null>(null)
  const [issueSummary, setIssueSummary] = useState('')
  const [servicing, setServicing] = useState<EquipmentAssetRecord | null>(null)
  const [serviceForm, setServiceForm] = useState<{
    event_date: string
    event_type: EquipmentServiceEventRecord['event_type']
    summary: string
    provider: string
    cost: number
    status_after: EquipmentAssetRecord['status'] | null
    next_service_date: string | null
  }>({
    event_date: today(), event_type: 'Maintenance', summary: '', provider: '',
    cost: 0, status_after: null, next_service_date: null,
  })
  const [eqHistoryId, setEqHistoryId] = useState('')

  const inventory = useQuery({
    queryKey: ['inventory', invSearch, invLocation, lowOnly, showInactive],
    queryFn: () => listInventory({
      search: invSearch, location_id: invLocation, low_stock: lowOnly,
      include_inactive: showInactive, limit: 500,
    }),
    enabled: online,
  })
  const invSummary = useQuery({
    queryKey: ['inventory-summary'], queryFn: getInventorySummary, enabled: online,
  })
  const invHistory = useQuery({
    queryKey: ['inventory-history', invHistoryId],
    queryFn: () => getInventoryHistory(invHistoryId),
    enabled: online && Boolean(invHistoryId),
  })

  const equipment = useQuery({
    queryKey: ['equipment', eqSearch, eqLocation, eqStatus, eqAttention, includeRetired],
    queryFn: () => listEquipment({
      search: eqSearch, location_id: eqLocation, status: eqStatus,
      attention_only: eqAttention, include_retired: includeRetired, limit: 500,
    }),
    enabled: online,
  })
  const eqSummary = useQuery({
    queryKey: ['equipment-summary'], queryFn: getEquipmentSummary, enabled: online,
  })
  const eqHistory = useQuery({
    queryKey: ['equipment-history', eqHistoryId],
    queryFn: () => getEquipmentHistory(eqHistoryId),
    enabled: online && Boolean(eqHistoryId),
  })

  async function refreshInventory() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ['inventory'] }),
      qc.invalidateQueries({ queryKey: ['inventory-summary'] }),
      qc.invalidateQueries({ queryKey: ['inventory-history'] }),
      qc.invalidateQueries({ queryKey: ['dashboard-attention-inventory'] }),
      qc.invalidateQueries({ queryKey: ['assets-summary'] }),
    ])
  }

  async function refreshEquipment() {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ['equipment'] }),
      qc.invalidateQueries({ queryKey: ['equipment-summary'] }),
      qc.invalidateQueries({ queryKey: ['equipment-history'] }),
      qc.invalidateQueries({ queryKey: ['dashboard-attention-equipment'] }),
      qc.invalidateQueries({ queryKey: ['assets-summary'] }),
    ])
  }

  const saveInventory = useMutation({
    mutationFn: () => editingInv
      ? updateInventoryItem(editingInv.id, {
          ...invForm, quantity: editingInv.quantity, version: editingInv.version,
        })
      : createInventoryItem(invForm),
    onSuccess: async () => {
      setInvFormOpen(false); setEditingInv(null)
      setInvForm(emptyInventory(session?.location.id || ''))
      await refreshInventory()
    },
  })

  const adjustInventory = useMutation({
    mutationFn: () => adjustInventoryItem(
      adjusting!, adjustMode, adjustQty, adjustReason, adjustNotes,
    ),
    onSuccess: async () => {
      setAdjusting(null); setAdjustQty(0); setAdjustNotes('')
      await refreshInventory()
    },
  })

  const saveEquipment = useMutation({
    mutationFn: () => editingEq
      ? updateEquipment(editingEq.id, { ...eqForm, version: editingEq.version })
      : createEquipment(eqForm),
    onSuccess: async () => {
      setEqFormOpen(false); setEditingEq(null)
      setEqForm(emptyEquipment(session?.location.id || ''))
      await refreshEquipment()
    },
  })

  const reportIssue = useMutation({
    mutationFn: () => reportEquipmentIssue(reporting!, issueSummary),
    onSuccess: async () => {
      setReporting(null); setIssueSummary('')
      await refreshEquipment()
    },
  })

  const addService = useMutation({
    mutationFn: () => addEquipmentService(servicing!, serviceForm),
    onSuccess: async () => {
      setServicing(null)
      setServiceForm({
        event_date: today(), event_type: 'Maintenance', summary: '', provider: '',
        cost: 0, status_after: null, next_service_date: null,
      })
      await refreshEquipment()
    },
  })

  function chooseTab(next: 'inventory' | 'equipment') {
    setTab(next)
    const params = new URLSearchParams(searchParams)
    params.set('tab', next)
    setSearchParams(params, { replace: true })
  }

  function startInventoryNew() {
    setEditingInv(null)
    setInvForm(emptyInventory(session?.location.id || ''))
    setInvFormOpen(true)
  }

  function startInventoryEdit(row: InventoryItemRecord) {
    setEditingInv(row)
    setInvForm({
      location_id: row.location_id, name: row.name, sku: row.sku,
      category: row.category, unit: row.unit, quantity: row.quantity,
      reorder_point: row.reorder_point, target_stock: row.target_stock,
      cost_per_unit: row.cost_per_unit, vendor: row.vendor,
      vendor_sku: row.vendor_sku, notes: row.notes, active: row.active,
    })
    setInvFormOpen(true)
  }

  function startEquipmentNew() {
    setEditingEq(null)
    setEqForm(emptyEquipment(session?.location.id || ''))
    setEqFormOpen(true)
  }

  function startEquipmentEdit(row: EquipmentAssetRecord) {
    setEditingEq(row)
    setEqForm({
      location_id: row.location_id, name: row.name, category: row.category,
      asset_tag: row.asset_tag, manufacturer: row.manufacturer, model: row.model,
      serial_number: row.serial_number, status: row.status,
      purchase_date: row.purchase_date, warranty_expiration: row.warranty_expiration,
      vendor: row.vendor, service_provider: row.service_provider,
      next_service_date: row.next_service_date, notes: row.notes, active: row.active,
    })
    setEqFormOpen(true)
  }

  const inventoryCategories = useMemo(
    () => [...new Set((inventory.data?.items || []).map(item => item.category))].sort(),
    [inventory.data?.items],
  )
  const equipmentCategories = useMemo(
    () => [...new Set((equipment.data?.equipment || []).map(item => item.category))].sort(),
    [equipment.data?.equipment],
  )

  return <section>
    <div className='page-heading'>
      <div>
        <h1>Inventory & Equipment</h1>
        <p className='muted'>
          Track supplies, stock levels, machines, equipment issues, and service history across all stores.
        </p>
      </div>
    </div>

    {!online && <div className='offline-banner'>Inventory & Equipment requires an online connection.</div>}

    <div className='hub-tabs' role='tablist'>
      <button className={'secondary ' + (tab === 'inventory' ? 'active' : '')} onClick={() => chooseTab('inventory')}>Inventory</button>
      <button className={'secondary ' + (tab === 'equipment' ? 'active' : '')} onClick={() => chooseTab('equipment')}>Equipment</button>
    </div>

    {tab === 'inventory' && <>
      {online && invSummary.data && <div className='metric-grid'>
        <div className='metric'><span>Active items</span><strong>{invSummary.data.active_items}</strong></div>
        <div className='metric'><span>Low stock</span><strong>{invSummary.data.low_stock}</strong></div>
        <div className='metric'><span>Out of stock</span><strong>{invSummary.data.out_of_stock}</strong></div>
        <div className='metric'><span>Stock value</span><strong>{'$'}{invSummary.data.stock_value.toFixed(2)}</strong></div>
      </div>}

      <div className='page-heading asset-subheading'>
        <div>
          <h2>Inventory</h2>
          <p className='muted'>Paper, toner, boxes, print media, supplies, and other consumables.</p>
        </div>
        {online && canManage && <button onClick={invFormOpen ? () => { setInvFormOpen(false); setEditingInv(null) } : startInventoryNew}>
          {invFormOpen ? 'Close' : 'New Inventory Item'}
        </button>}
      </div>

      {invFormOpen && online && canManage && <form className='panel form-grid' onSubmit={event => { event.preventDefault(); saveInventory.mutate() }}>
        <div className='span-2 section-heading'>
          <h3>{editingInv ? 'Edit Inventory Item' : 'New Inventory Item'}</h3>
          {editingInv && <span>Version {editingInv.version}</span>}
        </div>
        <label>Store<select required value={invForm.location_id} onChange={event => setInvForm(old => ({ ...old, location_id: event.target.value }))}>
          {allowedStores.map(store => <option key={store!.id} value={store!.id}>{store!.name} #{store!.store_number}</option>)}
        </select></label>
        <label>Category<input list='inventory-categories' required value={invForm.category} onChange={event => setInvForm(old => ({ ...old, category: event.target.value }))}/><datalist id='inventory-categories'>{inventoryCategories.map(value => <option key={value} value={value}/>)}</datalist></label>
        <label className='span-2'>Item name<input required maxLength={220} value={invForm.name} onChange={event => setInvForm(old => ({ ...old, name: event.target.value }))}/></label>
        <label>SKU / Item #<input maxLength={100} value={invForm.sku} onChange={event => setInvForm(old => ({ ...old, sku: event.target.value }))}/></label>
        <label>Unit<input maxLength={40} placeholder='each, roll, case, ream…' value={invForm.unit} onChange={event => setInvForm(old => ({ ...old, unit: event.target.value }))}/></label>
        <label>{editingInv ? 'Current quantity' : 'Initial quantity'}<input type='number' min='0' step='0.01' disabled={Boolean(editingInv)} value={editingInv ? editingInv.quantity : invForm.quantity} onChange={event => setInvForm(old => ({ ...old, quantity: Number(event.target.value) || 0 }))}/>{editingInv && <small className='muted'>Use Adjust Stock to change quantity.</small>}</label>
        <label>Reorder point<input type='number' min='0' step='0.01' value={invForm.reorder_point} onChange={event => setInvForm(old => ({ ...old, reorder_point: Number(event.target.value) || 0 }))}/></label>
        <label>Target stock<input type='number' min='0' step='0.01' value={invForm.target_stock} onChange={event => setInvForm(old => ({ ...old, target_stock: Number(event.target.value) || 0 }))}/></label>
        <label>Cost per unit ($)<input type='number' min='0' step='0.01' value={invForm.cost_per_unit} onChange={event => setInvForm(old => ({ ...old, cost_per_unit: Number(event.target.value) || 0 }))}/></label>
        <label>Vendor<input maxLength={180} value={invForm.vendor} onChange={event => setInvForm(old => ({ ...old, vendor: event.target.value }))}/></label>
        <label>Vendor item #<input maxLength={120} value={invForm.vendor_sku} onChange={event => setInvForm(old => ({ ...old, vendor_sku: event.target.value }))}/></label>
        <label className='span-2'>Notes<textarea rows={3} value={invForm.notes} onChange={event => setInvForm(old => ({ ...old, notes: event.target.value }))}/></label>
        <label className='checkbox'><input type='checkbox' checked={invForm.active} onChange={event => setInvForm(old => ({ ...old, active: event.target.checked }))}/>Active item</label>
        {saveInventory.error && <p className='error span-2'>{saveInventory.error instanceof Error ? saveInventory.error.message : 'Unable to save inventory item'}</p>}
        <div className='form-actions span-2'>
          <button disabled={saveInventory.isPending}>{saveInventory.isPending ? 'Saving…' : editingInv ? 'Save Item' : 'Create Item'}</button>
          <button type='button' className='secondary' onClick={() => { setInvFormOpen(false); setEditingInv(null) }}>Cancel</button>
        </div>
      </form>}

      {adjusting && online && <form className='panel form-grid' onSubmit={event => { event.preventDefault(); adjustInventory.mutate() }}>
        <div className='span-2 section-heading'>
          <div><h3>Adjust Stock · {adjusting.name}</h3><p className='muted'>Current: {adjusting.quantity} {adjusting.unit}</p></div>
          <button type='button' className='link-button' onClick={() => setAdjusting(null)}>Close</button>
        </div>
        <label>Adjustment<select value={adjustMode} onChange={event => setAdjustMode(event.target.value as 'add' | 'remove' | 'set')}>
          <option value='add'>Add to stock</option><option value='remove'>Remove from stock</option><option value='set'>Set exact count</option>
        </select></label>
        <label>{adjustMode === 'set' ? 'New count' : 'Quantity'}<input required min='0' step='0.01' type='number' value={adjustQty} onChange={event => setAdjustQty(Number(event.target.value) || 0)}/></label>
        <label>Reason<select value={adjustReason} onChange={event => setAdjustReason(event.target.value as (typeof inventoryReasons)[number])}>{inventoryReasons.map(value => <option key={value}>{value}</option>)}</select></label>
        <label className='span-2'>Notes<textarea rows={2} value={adjustNotes} onChange={event => setAdjustNotes(event.target.value)} placeholder='Optional receiving, usage, or count details'/></label>
        {adjustInventory.error && <p className='error span-2'>{adjustInventory.error instanceof Error ? adjustInventory.error.message : 'Unable to adjust stock'}</p>}
        <div className='form-actions span-2'><button disabled={adjustInventory.isPending}>{adjustInventory.isPending ? 'Saving…' : 'Save Adjustment'}</button></div>
      </form>}

      {invHistoryId && <div className='panel'>
        <div className='section-heading'><h3>Inventory History</h3><button className='link-button' onClick={() => setInvHistoryId('')}>Close</button></div>
        {invHistory.isLoading ? <p>Loading history…</p> : invHistory.data?.adjustments.length
          ? <div className='table-wrap'><table>
              <thead><tr><th>Date</th><th>Change</th><th>Result</th><th>Reason</th><th>Employee</th><th>Notes</th></tr></thead>
              <tbody>{invHistory.data.adjustments.map(row => <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td>{row.change_amount > 0 ? '+' : ''}{row.change_amount}</td>
                <td>{row.resulting_quantity}</td><td>{row.reason}</td>
                <td>{row.adjusted_by_name || '—'}</td><td>{row.notes || '—'}</td>
              </tr>)}</tbody>
            </table></div>
          : <p className='empty-state'>No stock adjustments recorded yet.</p>}
      </div>}

      <div className='toolbar order-filters'>
        <input placeholder='Search inventory…' value={invSearch} onChange={event => setInvSearch(event.target.value)}/>
        <select aria-label='Inventory store filter' value={invLocation} onChange={event => setInvLocation(event.target.value)}>
          <option value=''>All stores</option>
          {session?.locations.map(store => <option key={store.id} value={store.id}>{store.name} #{store.store_number}</option>)}
        </select>
        <label className='checkbox'><input type='checkbox' checked={lowOnly} onChange={event => setLowOnly(event.target.checked)}/>Low stock only</label>
        {canManage && <label className='checkbox'><input type='checkbox' checked={showInactive} onChange={event => setShowInactive(event.target.checked)}/>Show inactive</label>}
      </div>

      <div className='panel'>
        <div className='section-heading'><h3>Inventory Items</h3><span>{inventory.data?.total ?? 0} matching</span></div>
        {inventory.isLoading ? <p>Loading inventory…</p> : inventory.error
          ? <p className='error'>{inventory.error instanceof Error ? inventory.error.message : 'Unable to load inventory'}</p>
          : inventory.data?.items.length
            ? <div className='table-wrap'><table>
                <thead><tr><th>Item</th><th>Store</th><th>Category</th><th>On Hand</th><th>Reorder</th><th>Target</th><th>Status</th><th>Vendor</th><th>Actions</th></tr></thead>
                <tbody>{inventory.data.items.map(row => {
                  const canWrite = session?.employee.role === 'admin' || row.location_id === session?.location.id
                  return <tr key={row.id} className={row.out_of_stock ? 'overdue-row' : row.low_stock ? 'attention-row' : row.active ? undefined : 'inactive-row'}>
                    <td><strong>{row.name}</strong>{row.sku && <small className='issue-meta'>SKU: {row.sku}</small>}</td>
                    <td>{row.store ? row.store.name + ' #' + row.store.store_number : '—'}</td>
                    <td>{row.category}</td><td><strong>{row.quantity}</strong> {row.unit}</td>
                    <td>{row.reorder_point}</td><td>{row.target_stock || '—'}</td>
                    <td>{!row.active ? <span className='status-pill neutral'>Inactive</span>
                      : row.out_of_stock ? <span className='status-pill danger-pill'>Out of Stock</span>
                        : row.low_stock ? <span className='status-pill warning'>Low Stock</span>
                          : <span className='status-pill good'>OK</span>}</td>
                    <td>{row.vendor || '—'}{row.vendor_sku && <small className='issue-meta'>{row.vendor_sku}</small>}</td>
                    <td><div className='button-row table-actions'>
                      {online && canWrite && row.active && <button className='small-button' onClick={() => {
                        setAdjusting(row); setAdjustMode('add'); setAdjustQty(0); setAdjustReason('Received'); setAdjustNotes('')
                      }}>Adjust</button>}
                      <button className='small-button secondary' onClick={() => setInvHistoryId(row.id)}>History</button>
                      {online && canManage && canWrite && <button className='small-button secondary' onClick={() => startInventoryEdit(row)}>Edit</button>}
                    </div></td>
                  </tr>
                })}</tbody>
              </table></div>
            : <p className='empty-state'>No inventory items match these filters.</p>}
      </div>
    </>}

    {tab === 'equipment' && <>
      {online && eqSummary.data && <div className='metric-grid'>
        <div className='metric'><span>Active equipment</span><strong>{eqSummary.data.active_assets}</strong></div>
        <div className='metric'><span>Needs attention</span><strong>{eqSummary.data.needs_attention}</strong></div>
        <div className='metric'><span>Out of service</span><strong>{eqSummary.data.out_of_service}</strong></div>
        <div className='metric'><span>Service overdue</span><strong>{eqSummary.data.service_overdue}</strong></div>
      </div>}

      <div className='page-heading asset-subheading'>
        <div><h2>Equipment</h2><p className='muted'>Printers, cutters, laminators, computers, scales, and other store assets.</p></div>
        {online && canManage && <button onClick={eqFormOpen ? () => { setEqFormOpen(false); setEditingEq(null) } : startEquipmentNew}>
          {eqFormOpen ? 'Close' : 'New Equipment'}
        </button>}
      </div>

      {eqFormOpen && online && canManage && <form className='panel form-grid' onSubmit={event => { event.preventDefault(); saveEquipment.mutate() }}>
        <div className='span-2 section-heading'><h3>{editingEq ? 'Edit Equipment' : 'New Equipment'}</h3>{editingEq && <span>Version {editingEq.version}</span>}</div>
        <label>Store<select required value={eqForm.location_id} onChange={event => setEqForm(old => ({ ...old, location_id: event.target.value }))}>
          {allowedStores.map(store => <option key={store!.id} value={store!.id}>{store!.name} #{store!.store_number}</option>)}
        </select></label>
        <label>Category<input list='equipment-categories' required value={eqForm.category} onChange={event => setEqForm(old => ({ ...old, category: event.target.value }))}/><datalist id='equipment-categories'>{equipmentCategories.map(value => <option key={value} value={value}/>)}</datalist></label>
        <label className='span-2'>Equipment name<input required maxLength={220} value={eqForm.name} onChange={event => setEqForm(old => ({ ...old, name: event.target.value }))}/></label>
        <label>Asset tag<input maxLength={100} value={eqForm.asset_tag} onChange={event => setEqForm(old => ({ ...old, asset_tag: event.target.value }))}/></label>
        <label>Status<select value={eqForm.status} onChange={event => {
          const status = event.target.value as EquipmentAssetRecord['status']
          setEqForm(old => ({ ...old, status, active: status !== 'Retired' }))
        }}>{equipmentStatuses.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Manufacturer<input maxLength={120} value={eqForm.manufacturer} onChange={event => setEqForm(old => ({ ...old, manufacturer: event.target.value }))}/></label>
        <label>Model<input maxLength={160} value={eqForm.model} onChange={event => setEqForm(old => ({ ...old, model: event.target.value }))}/></label>
        <label>Serial number<input maxLength={160} value={eqForm.serial_number} onChange={event => setEqForm(old => ({ ...old, serial_number: event.target.value }))}/></label>
        <label>Purchase date<input type='date' value={eqForm.purchase_date || ''} onChange={event => setEqForm(old => ({ ...old, purchase_date: event.target.value || null }))}/></label>
        <label>Warranty expiration<input type='date' value={eqForm.warranty_expiration || ''} onChange={event => setEqForm(old => ({ ...old, warranty_expiration: event.target.value || null }))}/></label>
        <label>Next service date<input type='date' value={eqForm.next_service_date || ''} onChange={event => setEqForm(old => ({ ...old, next_service_date: event.target.value || null }))}/></label>
        <label>Vendor<input maxLength={180} value={eqForm.vendor} onChange={event => setEqForm(old => ({ ...old, vendor: event.target.value }))}/></label>
        <label>Service provider<input maxLength={180} value={eqForm.service_provider} onChange={event => setEqForm(old => ({ ...old, service_provider: event.target.value }))}/></label>
        <label className='span-2'>Notes<textarea rows={3} value={eqForm.notes} onChange={event => setEqForm(old => ({ ...old, notes: event.target.value }))}/></label>
        {saveEquipment.error && <p className='error span-2'>{saveEquipment.error instanceof Error ? saveEquipment.error.message : 'Unable to save equipment'}</p>}
        <div className='form-actions span-2'>
          <button disabled={saveEquipment.isPending}>{saveEquipment.isPending ? 'Saving…' : editingEq ? 'Save Equipment' : 'Create Equipment'}</button>
          <button type='button' className='secondary' onClick={() => { setEqFormOpen(false); setEditingEq(null) }}>Cancel</button>
        </div>
      </form>}

      {reporting && online && <form className='panel form-grid' onSubmit={event => { event.preventDefault(); reportIssue.mutate() }}>
        <div className='span-2 section-heading'>
          <div><h3>Report Equipment Issue · {reporting.name}</h3><p className='muted'>{reporting.store ? reporting.store.name + ' #' + reporting.store.store_number : ''}</p></div>
          <button type='button' className='link-button' onClick={() => setReporting(null)}>Close</button>
        </div>
        <label className='span-2'>What is wrong?<textarea required rows={3} value={issueSummary} onChange={event => setIssueSummary(event.target.value)} placeholder='Describe the problem, error message, symptoms, or what stopped working.'/></label>
        {reportIssue.error && <p className='error span-2'>{reportIssue.error instanceof Error ? reportIssue.error.message : 'Unable to report issue'}</p>}
        <div className='form-actions span-2'><button disabled={reportIssue.isPending}>{reportIssue.isPending ? 'Reporting…' : 'Report Issue'}</button></div>
      </form>}

      {servicing && online && canManage && <form className='panel form-grid' onSubmit={event => { event.preventDefault(); addService.mutate() }}>
        <div className='span-2 section-heading'>
          <div><h3>Log Service · {servicing.name}</h3><p className='muted'>Record maintenance, repairs, inspections, or service calls.</p></div>
          <button type='button' className='link-button' onClick={() => setServicing(null)}>Close</button>
        </div>
        <label>Service date<input required type='date' value={serviceForm.event_date} onChange={event => setServiceForm(old => ({ ...old, event_date: event.target.value }))}/></label>
        <label>Type<select value={serviceForm.event_type} onChange={event => setServiceForm(old => ({ ...old, event_type: event.target.value as EquipmentServiceEventRecord['event_type'] }))}>
          {equipmentEventTypes.filter(value => value !== 'Issue Reported').map(value => <option key={value}>{value}</option>)}
        </select></label>
        <label className='span-2'>Service summary<textarea required rows={3} value={serviceForm.summary} onChange={event => setServiceForm(old => ({ ...old, summary: event.target.value }))}/></label>
        <label>Provider / technician<input maxLength={180} value={serviceForm.provider} onChange={event => setServiceForm(old => ({ ...old, provider: event.target.value }))}/></label>
        <label>Cost ($)<input type='number' min='0' step='0.01' value={serviceForm.cost} onChange={event => setServiceForm(old => ({ ...old, cost: Number(event.target.value) || 0 }))}/></label>
        <label>Status after service<select value={serviceForm.status_after || ''} onChange={event => setServiceForm(old => ({ ...old, status_after: (event.target.value || null) as EquipmentAssetRecord['status'] | null }))}>
          <option value=''>No status change</option>{equipmentStatuses.map(value => <option key={value}>{value}</option>)}
        </select></label>
        <label>Next service date<input type='date' value={serviceForm.next_service_date || ''} onChange={event => setServiceForm(old => ({ ...old, next_service_date: event.target.value || null }))}/></label>
        {addService.error && <p className='error span-2'>{addService.error instanceof Error ? addService.error.message : 'Unable to log service'}</p>}
        <div className='form-actions span-2'><button disabled={addService.isPending}>{addService.isPending ? 'Saving…' : 'Log Service'}</button></div>
      </form>}

      {eqHistoryId && <div className='panel'>
        <div className='section-heading'><h3>Equipment Service History</h3><button className='link-button' onClick={() => setEqHistoryId('')}>Close</button></div>
        {eqHistory.isLoading ? <p>Loading history…</p> : eqHistory.data?.events.length
          ? <div className='table-wrap'><table>
              <thead><tr><th>Date</th><th>Type</th><th>Summary</th><th>Provider</th><th>Cost</th><th>Recorded By</th></tr></thead>
              <tbody>{eqHistory.data.events.map(row => <tr key={row.id}>
                <td>{row.event_date}</td><td>{row.event_type}</td><td className='wrap-cell'>{row.summary}</td>
                <td>{row.provider || '—'}</td><td>{'$'}{row.cost.toFixed(2)}</td><td>{row.recorded_by_name || '—'}</td>
              </tr>)}</tbody>
            </table></div>
          : <p className='empty-state'>No equipment history recorded yet.</p>}
      </div>}

      <div className='toolbar order-filters'>
        <input placeholder='Search equipment…' value={eqSearch} onChange={event => setEqSearch(event.target.value)}/>
        <select aria-label='Equipment store filter' value={eqLocation} onChange={event => setEqLocation(event.target.value)}>
          <option value=''>All stores</option>{session?.locations.map(store => <option key={store.id} value={store.id}>{store.name} #{store.store_number}</option>)}
        </select>
        <select aria-label='Equipment status filter' value={eqStatus} onChange={event => setEqStatus(event.target.value)}>
          <option value=''>All active statuses</option>{equipmentStatuses.map(value => <option key={value}>{value}</option>)}
        </select>
        <label className='checkbox'><input type='checkbox' checked={eqAttention} onChange={event => setEqAttention(event.target.checked)}/>Needs attention only</label>
        {canManage && <label className='checkbox'><input type='checkbox' checked={includeRetired} onChange={event => setIncludeRetired(event.target.checked)}/>Include retired</label>}
      </div>

      <div className='panel'>
        <div className='section-heading'><h3>Equipment</h3><span>{equipment.data?.total ?? 0} matching</span></div>
        {equipment.isLoading ? <p>Loading equipment…</p> : equipment.error
          ? <p className='error'>{equipment.error instanceof Error ? equipment.error.message : 'Unable to load equipment'}</p>
          : equipment.data?.equipment.length
            ? <div className='table-wrap'><table>
                <thead><tr><th>Equipment</th><th>Store</th><th>Status</th><th>Asset / Serial</th><th>Next Service</th><th>Provider</th><th>Actions</th></tr></thead>
                <tbody>{equipment.data.equipment.map(row => {
                  const canWrite = session?.employee.role === 'admin' || row.location_id === session?.location.id
                  const rowClass = row.status === 'Out of Service' || row.service_overdue ? 'overdue-row'
                    : row.status === 'Needs Attention' ? 'attention-row'
                      : row.status === 'Retired' ? 'inactive-row' : undefined
                  return <tr key={row.id} className={rowClass}>
                    <td><strong>{row.name}</strong><small className='issue-meta'>{[row.manufacturer, row.model].filter(Boolean).join(' ') || row.category}</small></td>
                    <td>{row.store ? row.store.name + ' #' + row.store.store_number : '—'}</td>
                    <td><span className={'status-pill ' + (row.status === 'Operational' ? 'good' : row.status === 'Needs Attention' ? 'warning' : row.status === 'Out of Service' ? 'danger-pill' : 'neutral')}>{row.status}</span></td>
                    <td>{row.asset_tag || '—'}{row.serial_number && <small className='issue-meta'>S/N {row.serial_number}</small>}</td>
                    <td>{row.next_service_date || 'Not scheduled'}{row.service_overdue && <small className='issue-meta'>Overdue</small>}{row.service_due_30 && !row.service_overdue && <small className='issue-meta'>Due within 30 days</small>}</td>
                    <td>{row.service_provider || '—'}</td>
                    <td><div className='button-row table-actions'>
                      {online && canWrite && row.status !== 'Retired' && <button className='small-button' onClick={() => { setReporting(row); setIssueSummary('') }}>Report Issue</button>}
                      <button className='small-button secondary' onClick={() => setEqHistoryId(row.id)}>History</button>
                      {online && canManage && canWrite && row.status !== 'Retired' && <button className='small-button secondary' onClick={() => {
                        setServicing(row)
                        setServiceForm({
                          event_date: today(), event_type: 'Maintenance', summary: '',
                          provider: row.service_provider, cost: 0, status_after: null,
                          next_service_date: row.next_service_date,
                        })
                      }}>Log Service</button>}
                      {online && canManage && canWrite && <button className='small-button secondary' onClick={() => startEquipmentEdit(row)}>Edit</button>}
                    </div></td>
                  </tr>
                })}</tbody>
              </table></div>
            : <p className='empty-state'>No equipment matches these filters.</p>}
      </div>
    </>}
  </section>
}
