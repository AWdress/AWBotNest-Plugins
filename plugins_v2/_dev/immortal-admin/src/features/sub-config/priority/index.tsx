import { ArrowDown01 } from 'lucide-react'
import { useUIStore } from '@/stores/ui-store'
import { ContentSection } from '@/features/settings/components/content-section.tsx'
import PriorityManager from '@/features/sub-config/priority/priority-manager.tsx'

export function SubConfigPriority() {
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <ContentSection
      title={isSimple ? '优先级' : '序位阵'}
      desc={
        isSimple
          ? '设置订阅的优先级顺序。'
          : '为目标定下先后次序，使强者先行、要者先至。'
      }
      icon={<ArrowDown01 className='h-5 w-5 text-primary' />}
    >
      <PriorityManager />
    </ContentSection>
  )
}
