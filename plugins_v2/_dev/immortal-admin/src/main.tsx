import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createRouter, createHashHistory } from '@tanstack/react-router'
import { waitForHost } from '@/lib/host-bridge'
import { handleServerError } from '@/lib/handle-server-error'
import { DirectionProvider } from './context/direction-provider'
import { FontProvider } from './context/font-provider'
import { ThemeProvider } from './context/theme-provider'
import { ImageModeProvider } from '@/context/image-mode-provider'
import { routeTree } from './routeTree.gen'
import './styles/index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, staleTime: 10000 },
    mutations: { onError: handleServerError },
  },
  queryCache: new QueryCache({ onError: handleServerError }),
})
const router = createRouter({ routeTree, history: createHashHistory(), context: { queryClient }, defaultPreload: 'intent', defaultPreloadStaleTime: 0 })
declare module '@tanstack/react-router' { interface Register { router: typeof router } }
async function boot() {
  const root = ReactDOM.createRoot(document.getElementById('root')!)
  root.render(<p className='p-6 text-sm' role='status'>正在连接平台…</p>)
  try { await waitForHost() } catch (error) {
    root.render(<div className='space-y-3 p-6 text-sm' role='alert'><h1 className='font-semibold'>无法打开 Immortal</h1><p>{error instanceof Error ? error.message : '请重新打开插件配置页。'}</p></div>)
    return
  }
  root.render(<StrictMode><QueryClientProvider client={queryClient}><ThemeProvider><FontProvider><ImageModeProvider><DirectionProvider><RouterProvider router={router} /></DirectionProvider></ImageModeProvider></FontProvider></ThemeProvider></QueryClientProvider></StrictMode>)
}
void boot()
