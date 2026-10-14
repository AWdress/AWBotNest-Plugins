import { Bell } from 'lucide-react'
import { ContentSection } from '@/features/settings/components/content-section'
export function SettingsNotifications() {
  return <ContentSection title='平台通知' desc='使用 AWBotNest 已配置的通知渠道。' icon={<Bell className='h-5 w-5 text-primary' />}>
    <div className='max-w-prose space-y-3 text-sm leading-6'>
      <p>请在平台“通知设置”中配置 Telegram、企业微信等渠道，不需要在 Immortal 再填写 Bot Token 或企业凭证。</p>
      <p className='text-muted-foreground'>要接收采集和任务结果，请在本插件的“插件设置”中启用“任务结果通知”，然后保存。</p>
    </div>
  </ContentSection>
}
