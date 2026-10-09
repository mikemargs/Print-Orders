import { SummaryCard } from '../../components/SummaryCard'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getEquipmentSummary } from '../../api/equipment'
import { getInventorySummary } from '../../api/inventory'
import { useOnline } from '../../offline/OnlineState'

export function AssetsSummary(){
  const {online}=useOnline()
  const inventory=useQuery({queryKey:['assets-summary','inventory'],queryFn:getInventorySummary,enabled:online,refetchInterval:30000})
  const equipment=useQuery({queryKey:['assets-summary','equipment'],queryFn:getEquipmentSummary,enabled:online,refetchInterval:30000})
  const loading=inventory.isLoading||equipment.isLoading
  const failed=inventory.error||equipment.error
  return <div className="panel issue-summary">
    <div className="section-heading"><h2>Inventory & Equipment</h2><Link to="/assets">Open workspace</Link></div>
    {!online?<p className="muted">Inventory and equipment status requires an online connection.</p>:loading?<p>Loading inventory and equipment status…</p>:failed?<p className="error">Unable to load inventory and equipment status.</p>:<>
      <div className="metric-grid">
        <SummaryCard to="/assets?tab=inventory&view=low"><span>Low stock</span><strong>{inventory.data?.low_stock??0}</strong></SummaryCard>
        <SummaryCard to="/assets?tab=inventory&view=out"><span>Out of stock</span><strong>{inventory.data?.out_of_stock??0}</strong></SummaryCard>
        <SummaryCard to="/assets?tab=equipment&view=attention"><span>Equipment attention</span><strong>{(equipment.data?.needs_attention??0)+(equipment.data?.out_of_service??0)}</strong></SummaryCard>
        <SummaryCard to="/assets?tab=equipment&view=service_overdue"><span>Service overdue</span><strong>{equipment.data?.service_overdue??0}</strong></SummaryCard>
      </div>
    </>}
  </div>
}
