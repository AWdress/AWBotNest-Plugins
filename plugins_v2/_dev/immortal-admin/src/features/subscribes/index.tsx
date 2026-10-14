import { Heart } from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search.tsx'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch'
import { useUIStore } from '@/stores/ui-store'
import { SubscribeList } from '@/features/subscribes/subscribe-list.tsx'

export function Subscribes() {
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
          title={isSimple ? '订阅管理' : '灵契簿'}
          description={
            isSimple
              ? '管理影片、演员和综合订阅，了解订阅状态。'
              : '统摄影片、演员与综合订阅，观其流转与停转。'
          }
          icon={<Heart className='h-8 w-8 text-primary' />}
        />
        <SubscribeList />
      </Main>
    </>
  )
}
