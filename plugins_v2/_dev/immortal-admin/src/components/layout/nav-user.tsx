import { SidebarMenu, SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar'
export function NavUser({ user }: { user: { name: string } }) {
  return <SidebarMenu><SidebarMenuItem><SidebarMenuButton size='lg' className='cursor-default'>
    <div className='grid flex-1 text-start text-sm leading-tight'>
      <span className='truncate font-semibold'>{user.name}</span>
      <span className='mt-1 text-xs text-muted-foreground'>由 AWBotNest 管理</span>
    </div>
  </SidebarMenuButton></SidebarMenuItem></SidebarMenu>
}
