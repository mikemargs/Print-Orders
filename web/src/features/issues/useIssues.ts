import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSession } from '../../auth/SessionContext'
import { useOnline } from '../../offline/OnlineState'
export function useIssueQuery<T>(key:unknown[],load:()=>Promise<T>,enabled=true){
 const {session}=useSession();const {online}=useOnline()
 return useQuery({queryKey:['issues',session?.company.id,session?.employee.id,session?.location.id,...key],queryFn:load,enabled:!!session&&online&&enabled,refetchInterval:online?30_000:false,refetchIntervalInBackground:false,refetchOnWindowFocus:true,retry:1})
}
export function useRefreshIssues(){const client=useQueryClient();return ()=>Promise.all([client.invalidateQueries({queryKey:['issues']}),client.invalidateQueries({queryKey:['customer-profile-counts']})])}
