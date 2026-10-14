import { Heart } from 'lucide-react'
import { useUIStore } from '@/stores/ui-store'
import { ContentSection } from '@/features/settings/components/content-section.tsx'
import { PreferenceManager } from '@/features/sub-config/preference/preference-manager.tsx'

export function SubConfigPreference() {
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <ContentSection
      title={isSimple ? '偏好设置' : '灵犀偏好'}
      desc={
        isSimple
          ? '保存创建订阅时的默认偏好设置。'
          : '保存 bot 创建演员订阅和综合订阅时可复用的默认偏好。'
      }
      icon={<Heart className='h-5 w-5 text-primary' />}
    >
      <PreferenceManager />
    </ContentSection>
  )
}
