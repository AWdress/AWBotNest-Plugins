import { BookCheck } from 'lucide-react'
import { ConfigDrawer } from '@/components/config-drawer'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch'
import { useUIStore } from '@/stores/ui-store'
import TaskManager from '@/features/tasks/components/task-manager.tsx'

export function Tasks() {
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
          title={isSimple ? '任务管理' : '时轮殿'}
          description={
            isSimple
              ? '查看和管理所有任务，包括进行中和已完成的任务。'
              : '依时开阵，驱动诸务自行轮转。'
          }
          icon={<BookCheck className='h-8 w-8 text-primary' />}
        />
        <TaskManager />
      </Main>
    </>
  )
}
