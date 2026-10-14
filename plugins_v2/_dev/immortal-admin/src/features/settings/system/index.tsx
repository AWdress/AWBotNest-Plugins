import { Cog } from 'lucide-react'
import { ContentSection } from '@/features/settings/components/content-section'
import { SystemConfigForm } from './system-config-form'
import { RouteNamingForm } from './route-naming-form'
export function SettingsSystem() {
  return <div className='space-y-6'>
    <ContentSection title='采集连接设置' desc='仅影响 Immortal 的采集连接，不修改平台。留空时使用平台网络设置。' icon={<Cog className='h-5 w-5 text-primary' />}>
      <SystemConfigForm />
    </ContentSection>
    <RouteNamingForm />
    <p className='max-w-prose text-sm leading-6 text-muted-foreground'>登录、更新、机器人和通知渠道由 AWBotNest 管理。本插件不启动独立 Bot，不提供 SQL 执行器。</p>
  </div>
}
