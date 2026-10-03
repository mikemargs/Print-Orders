import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { SessionProvider } from './auth/SessionContext'
import { OnlineProvider } from './offline/OnlineState'
import './styles.css'
import './print.css'

const queryClient=new QueryClient({defaultOptions:{queries:{staleTime:15_000,retry:1}}})
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={queryClient}><BrowserRouter><OnlineProvider><SessionProvider><App/></SessionProvider></OnlineProvider></BrowserRouter></QueryClientProvider></React.StrictMode>)
