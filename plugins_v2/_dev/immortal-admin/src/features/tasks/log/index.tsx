import { ScrollText } from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer.tsx'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header.tsx'
import { Main } from '@/components/layout/main.tsx'
import { Search } from '@/components/search.tsx'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch.tsx'
import { useUIStore } from '@/stores/ui-store'
import { TaskLogTable } from '@/features/tasks/log/task-log.tsx'

export function TaskLog() {
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
          title={isSimple ? '任务日志' : '运转录'}
          description={
            isSimple
              ? '查看所有任务的执行记录。'
              : '凡已取回之物，皆录于此，以观得失。'
          }
          icon={<ScrollText className='h-8 w-8 text-primary' />}
        ></ContentTitle>
        <TaskLogTable />
      </Main>
    </>
  )
}
