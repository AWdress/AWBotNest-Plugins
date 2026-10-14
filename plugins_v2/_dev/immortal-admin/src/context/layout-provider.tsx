import { createContext, useContext, useState } from 'react'
import { getCookie, setCookie } from '@/lib/cookies'

export type Collapsible = 'offcanvas' | 'icon' | 'none'
export type Variant = 'sidebar' | 'floating'
export type MobileNavigation = 'bottom-nav' | 'sidebar'

// Cookie constants following the pattern from sidebar.tsx
const LAYOUT_COLLAPSIBLE_COOKIE_NAME = 'layout_collapsible'
const LAYOUT_VARIANT_COOKIE_NAME = 'layout_variant'
const MOBILE_NAVIGATION_COOKIE_NAME = 'mobile_navigation'
const LAYOUT_COOKIE_MAX_AGE = 60 * 60 * 24 * 7 // 7 days

// Default values
const DEFAULT_VARIANT = 'floating'
const DEFAULT_COLLAPSIBLE = 'icon'
const DEFAULT_MOBILE_NAVIGATION = 'bottom-nav'

type LayoutContextType = {
  resetLayout: () => void

  defaultCollapsible: Collapsible
  collapsible: Collapsible
  setCollapsible: (collapsible: Collapsible) => void

  defaultVariant: Variant
  variant: Variant
  setVariant: (variant: Variant) => void

  defaultMobileNavigation: MobileNavigation
  mobileNavigation: MobileNavigation
  setMobileNavigation: (mobileNavigation: MobileNavigation) => void
}

const LayoutContext = createContext<LayoutContextType | null>(null)

type LayoutProviderProps = {
  children: React.ReactNode
}

export function LayoutProvider({ children }: LayoutProviderProps) {
  const [collapsible, _setCollapsible] = useState<Collapsible>(() => {
    const saved = getCookie(LAYOUT_COLLAPSIBLE_COOKIE_NAME)
    return (saved as Collapsible) || DEFAULT_COLLAPSIBLE
  })

  const [variant, _setVariant] = useState<Variant>(() => {
    const saved = getCookie(LAYOUT_VARIANT_COOKIE_NAME)
    return (saved as Variant) || DEFAULT_VARIANT
  })

  const [mobileNavigation, _setMobileNavigation] = useState<MobileNavigation>(() => {
    const saved = getCookie(MOBILE_NAVIGATION_COOKIE_NAME)
    return (saved as MobileNavigation) || DEFAULT_MOBILE_NAVIGATION
  })

  const setCollapsible = (newCollapsible: Collapsible) => {
    _setCollapsible(newCollapsible)
    setCookie(
      LAYOUT_COLLAPSIBLE_COOKIE_NAME,
      newCollapsible,
      LAYOUT_COOKIE_MAX_AGE
    )
  }

  const setVariant = (newVariant: Variant) => {
    _setVariant(newVariant)
    setCookie(LAYOUT_VARIANT_COOKIE_NAME, newVariant, LAYOUT_COOKIE_MAX_AGE)
  }

  const setMobileNavigation = (newMobileNavigation: MobileNavigation) => {
    _setMobileNavigation(newMobileNavigation)
    setCookie(
      MOBILE_NAVIGATION_COOKIE_NAME,
      newMobileNavigation,
      LAYOUT_COOKIE_MAX_AGE
    )
  }

  const resetLayout = () => {
    setCollapsible(DEFAULT_COLLAPSIBLE)
    setVariant(DEFAULT_VARIANT)
    setMobileNavigation(DEFAULT_MOBILE_NAVIGATION)
  }

  const contextValue: LayoutContextType = {
    resetLayout,
    defaultCollapsible: DEFAULT_COLLAPSIBLE,
    collapsible,
    setCollapsible,
    defaultVariant: DEFAULT_VARIANT,
    variant,
    setVariant,
    defaultMobileNavigation: DEFAULT_MOBILE_NAVIGATION,
    mobileNavigation,
    setMobileNavigation,
  }

  return <LayoutContext value={contextValue}>{children}</LayoutContext>
}

// Define the hook for the provider
// eslint-disable-next-line react-refresh/only-export-components
export function useLayout() {
  const context = useContext(LayoutContext)
  if (!context) {
    throw new Error('useLayout must be used within a LayoutProvider')
  }
  return context
}
