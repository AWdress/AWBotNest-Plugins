import { Route } from 'lucide-react'
import { useUIStore } from '@/stores/ui-store'
import { ContentSection } from '@/features/settings/components/content-section.tsx'
import RulesManager from '@/features/settings/rule/rule-manager.tsx'

export function SettingsRule() {
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <ContentSection
      title={isSimple ? '规则管理' : '流转法则'}
      desc={
        isSimple
          ? '配置资源归类和流转规则。'
          : '一经立定，资源便会循着既定路径流转。'
      }
      icon={<Route className='h-5 w-5 text-primary' />}
    >
      <RulesManager />
    </ContentSection>
  )
}
