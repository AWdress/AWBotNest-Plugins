import { Outlet } from '@tanstack/react-router'
import { ArrowDown01, Heart, ListFilterPlus, Star } from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer.tsx'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header.tsx'
import { Main } from '@/components/layout/main.tsx'
import { Search } from '@/components/search.tsx'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch.tsx'
import { TopNav } from '@/features/settings/components/top-nav.tsx'
import { useUIStore } from '@/stores/ui-store'

const fantasyNavItems = [
  {
    title: '筛灵阵',
    href: '/sub-config',
    icon: <ListFilterPlus size={18} />,
  },
  {
    title: '序位阵',
    href: '/sub-config/priority',
    icon: <ArrowDown01 size={18} />,
  },
  {
    title: '灵犀偏好',
    href: '/sub-config/preference',
    icon: <Heart size={18} />,
  },
]

const simpleNavItems = [
  {
    title: '过滤器',
    href: '/sub-config',
    icon: <ListFilterPlus size={18} />,
  },
  {
    title: '优先级',
    href: '/sub-config/priority',
    icon: <ArrowDown01 size={18} />,
  },
  {
    title: '偏好设置',
    href: '/sub-config/preference',
    icon: <Heart size={18} />,
  },
]

export function SubConfig() {
  const routeNamingMode = useUIStore((state) => state.routeNamingMode)
  const navItems = routeNamingMode === 'simple' ? simpleNavItems : fantasyNavItems

  return (
    <>
      <Header fixed>
        <Search />
        <div className='ms-auto flex items-center space-x-4'>
          <ServerLogDialog />
          <ImageModeSwitch />
          <ThemeSwitch />
          <ConfigDrawer />
        </div>
      </Header>

      <Main fixed>
        <ContentTitle
          title={routeNamingMode === 'simple' ? '订阅配置' : '灵枢阁'}
          description={
            routeNamingMode === 'simple'
              ? '配置过滤规则、优先级和默认偏好。'
              : '统摄过滤、排序与订阅偏好，使灵契依律而行。'
          }
          icon={<Star className='h-8 w-8 text-primary' />}
        />
        <div className='flex h-full flex-col overflow-hidden'>
          <div className='shrink-0'>
            <TopNav items={navItems} />
          </div>
          <div
            className='scrollbar-hide flex-1 overflow-auto'
            data-main-scroll-container
          >
            <Outlet />
          </div>
        </div>
      </Main>
    </>
  )
}
