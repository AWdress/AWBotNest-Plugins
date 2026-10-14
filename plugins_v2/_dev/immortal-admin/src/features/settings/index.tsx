import { Outlet } from '@tanstack/react-router'
import {
  Bell,
  Cog,
  Download,
  Route,
  Server,
  Settings2,
  UserPen,
} from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch'
import { TopNav } from '@/features/settings/components/top-nav.tsx'
import { useUIStore } from '@/stores/ui-store'

const fantasyNavItems = [
  {
    title: '身份簿',
    href: '/settings',
    icon: <UserPen size={18} />,
  },
  {
    title: '流转法则',
    href: '/settings/rule',
    icon: <Route size={18} />,
  },
  {
    title: '下载法器',
    href: '/settings/downloader',
    icon: <Download size={18} />,
  },
  {
    title: '媒资洞府',
    href: '/settings/media-server',
    icon: <Server size={18} />,
  },
  {
    title: '传讯法阵',
    href: '/settings/notifications',
    icon: <Bell size={18} />,
  },
  {
    title: '天道细则',
    href: '/settings/system',
    icon: <Cog size={18} />,
  },
]

const simpleNavItems = [
  {
    title: '账号',
    href: '/settings',
    icon: <UserPen size={18} />,
  },
  {
    title: '规则',
    href: '/settings/rule',
    icon: <Route size={18} />,
  },
  {
    title: '下载器',
    href: '/settings/downloader',
    icon: <Download size={18} />,
  },
  {
    title: '媒体服务器',
    href: '/settings/media-server',
    icon: <Server size={18} />,
  },
  {
    title: '通知',
    href: '/settings/notifications',
    icon: <Bell size={18} />,
  },
  {
    title: '系统',
    href: '/settings/system',
    icon: <Cog size={18} />,
  },
]

export function Settings() {
  const routeNamingMode = useUIStore((state) => state.routeNamingMode)
  const navItems = routeNamingMode === 'simple' ? simpleNavItems : fantasyNavItems

  return (
    <>
      <Header>
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
          title={routeNamingMode === 'simple' ? '系统设置' : '道枢殿'}
          description={
            routeNamingMode === 'simple'
              ? '管理系统设置、下载器、通知和订阅规则。'
              : '统御下载、媒资、通知与系统法则，调理洞府运转。'
          }
          icon={<Settings2 className='h-8 w-8 text-primary' />}
        />
        <div className='flex min-h-0 flex-1 flex-col overflow-hidden'>
          <div className='shrink-0'>
            <TopNav items={navItems} />
          </div>
          <div
            className='scrollbar-hide flex-1 overflow-auto md:pb-0'
            data-main-scroll-container
          >
            <Outlet />
          </div>
        </div>
      </Main>
    </>
  )
}
