import { Database } from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search.tsx'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch'
import { useUIStore } from '@/stores/ui-store'
import { SubscribeSearch } from '@/features/subscribes/subscribe-search.tsx'

export function SubscribeSearchPage() {
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

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
          title={isSimple ? '订阅搜索' : '巡天鉴'}
          description={
            isSimple
              ? '按番号、演员等条件搜索可订阅的影片。'
              : '按番号、演员与诸般条件巡检可订之作。'
          }
          icon={<Database className='h-8 w-8 text-primary' />}
        />
        <SubscribeSearch />
      </Main>
    </>
  )
}
