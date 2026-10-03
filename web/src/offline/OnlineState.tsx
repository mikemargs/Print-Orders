import { createContext, useContext, useEffect, useState, type PropsWithChildren } from 'react'
import { lastSync } from './db'

interface OnlineValue { online: boolean; lastSyncAt: string }
const OnlineContext = createContext<OnlineValue>({ online: true, lastSyncAt: '' })
export const useOnline = () => useContext(OnlineContext)

export function OnlineProvider({ children }: PropsWithChildren) {
  const [online,setOnline]=useState(navigator.onLine); const [lastSyncAt,setLastSync]=useState('')
  useEffect(() => {
    const refresh=()=>void lastSync().then(setLastSync)
    const on=()=>{setOnline(true);refresh()}; const off=()=>{setOnline(false);refresh()}
    window.addEventListener('online',on); window.addEventListener('offline',off)
    window.addEventListener('print-orders-online',on); window.addEventListener('print-orders-offline',off); refresh()
    return()=>{window.removeEventListener('online',on);window.removeEventListener('offline',off);window.removeEventListener('print-orders-online',on);window.removeEventListener('print-orders-offline',off)}
  },[])
  return <OnlineContext.Provider value={{online,lastSyncAt}}>{children}</OnlineContext.Provider>
}
