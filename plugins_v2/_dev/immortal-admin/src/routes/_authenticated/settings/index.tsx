import { createFileRoute } from '@tanstack/react-router'
import { UserRound } from 'lucide-react'
import { ContentSection } from '@/features/settings/components/content-section'
function PlatformAccount() {
  return <ContentSection title='平台管理账户' desc='Immortal 已内置到 AWBotNest，无需单独注册或登录。' icon={<UserRound className='h-5 w-5 text-primary' />}>
    <p className='max-w-prose text-sm leading-6 text-muted-foreground'>账户与权限由平台统一管理。请到 AWBotNest 的账户设置修改密码；本插件不会修改平台账号。</p>
  </ContentSection>
}
export const Route = createFileRoute('/_authenticated/settings/')({ component: PlatformAccount })
