import { Server } from 'lucide-react'
import { useUIStore } from '@/stores/ui-store'
import { ContentSection } from '@/features/settings/components/content-section.tsx'
import { MediaServerForm } from './media-server-form.tsx'

export function SettingsMediaServer() {
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <ContentSection
      title={isSimple ? '媒体服务器' : '媒资洞府'}
      desc={
        isSimple
          ? '连接 Emby、Jellyfin、Plex、极影视等媒体服务器。'
          : '连接 Emby、Jellyfin、Plex、极影视等媒资洞府。'
      }
      icon={<Server className='h-5 w-5 text-primary' />}
    >
      <MediaServerForm />
    </ContentSection>
  )
}
