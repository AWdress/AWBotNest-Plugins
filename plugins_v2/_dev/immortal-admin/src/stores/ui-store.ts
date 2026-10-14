import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type RouteNamingMode = 'simple' | 'fantasy'

interface UIState {
  hideBottomNav: boolean
  setHideBottomNav: (hide: boolean) => void
  routeNamingMode: RouteNamingMode
  setRouteNamingMode: (mode: RouteNamingMode) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      hideBottomNav: false,
      setHideBottomNav: (hide) => set({ hideBottomNav: hide }),
      routeNamingMode: 'simple',
      setRouteNamingMode: (mode) => set({ routeNamingMode: mode }),
    }),
    {
      name: 'awbotnest-immortal-ui-settings',
    }
  )
)
