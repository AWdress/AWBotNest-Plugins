import { ListFilterPlus } from 'lucide-react'
import { useUIStore } from '@/stores/ui-store'
import { ContentSection } from '@/features/settings/components/content-section.tsx'
import { FilterManager } from '@/features/sub-config/filter/filter-manager.tsx'

export function SubConfigFilter() {
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <ContentSection
      title={isSimple ? '过滤器' : '筛灵阵'}
      desc={
        isSimple
          ? '配置过滤条件，排除不需要的资源。'
          : '筛尽浮尘与杂气，只留真正值得纳入的目标。'
      }
      icon={<ListFilterPlus className='h-5 w-5 text-primary' />}
    >
      <FilterManager />
    </ContentSection>
  )
}
