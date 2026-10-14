import { Outlet } from '@tanstack/react-router'
import { getCookie } from '@/lib/cookies'
import { cn } from '@/lib/utils'
import { LayoutProvider, useLayout } from '@/context/layout-provider'
import { SearchProvider } from '@/context/search-provider'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import AppBottomNav from '@/components/layout/app-bottom-nav.tsx'
import { AppSidebar } from '@/components/layout/app-sidebar'
import { SkipToMain } from '@/components/skip-to-main'

type AuthenticatedLayoutProps = {
  children?: React.ReactNode
}

function AuthenticatedLayoutContent({ children }: AuthenticatedLayoutProps) {
  const defaultOpen = getCookie('sidebar_state') !== 'false'
  const isMobile = useIsMobile()
  const { mobileNavigation } = useLayout()
  const showMobileSidebar = isMobile && mobileNavigation === 'sidebar'

  return (
    <SidebarProvider defaultOpen={defaultOpen}>
      <SkipToMain />
      {(!isMobile || showMobileSidebar) && <AppSidebar />}
      <SidebarInset
        data-mobile-navigation={isMobile ? mobileNavigation : undefined}
        className={cn(
          '@container/content',
          'has-data-[layout=fixed]:h-dvh',
          'peer-data-[variant=inset]:has-data-[layout=fixed]:h-[calc(100dvh-(var(--spacing)*4))]'
        )}
      >
        {children ?? <Outlet />}
      </SidebarInset>
      {isMobile && mobileNavigation === 'bottom-nav' && <AppBottomNav />}
    </SidebarProvider>
  )
}

export function AuthenticatedLayout({ children }: AuthenticatedLayoutProps) {
  return (
    <SearchProvider>
      <LayoutProvider>
        <AuthenticatedLayoutContent>{children}</AuthenticatedLayoutContent>
      </LayoutProvider>
    </SearchProvider>
  )
}
