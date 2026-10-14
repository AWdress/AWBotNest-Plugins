import { Swords } from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch'
import { useUIStore } from '@/stores/ui-store'
import { DownloadLogTable } from '@/features/download-log/download-table.tsx'

export function DownloadLog() {
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
          title={isSimple ? '下载日志' : '历练录'}
          description={
            isSimple
              ? '查看所有下载任务的执行记录。'
              : '凡已取回之物，皆录于此，以观得失。'
          }
          icon={<Swords className='h-8 w-8 text-primary' />}
        />
        <DownloadLogTable />
      </Main>
    </>
  )
}
