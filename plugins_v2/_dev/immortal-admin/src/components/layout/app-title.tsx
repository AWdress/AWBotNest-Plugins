import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'

const brandLogo = `${import.meta.env.BASE_URL}hulu_vector_64.png?v=20260321`

export function AppTitle() {
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          size='lg'
          className='h-auto gap-3 rounded-xl border border-sidebar-border/70 bg-sidebar-accent/30 px-2.5 py-2 shadow-sm hover:bg-sidebar-accent/60 active:bg-sidebar-accent/60'
          asChild
        >
          <div>
            <div className='flex size-10 shrink-0 items-center justify-center rounded-2xl bg-white shadow-[0_12px_28px_rgba(15,15,15,0.14)] ring-1 ring-black/8'>
              <img
                src={brandLogo}
                alt='青灯不灭'
                data-image-mode-exempt='true'
                className='size-7 object-contain'
              />
            </div>
            <div className='grid flex-1 text-left leading-none group-data-[collapsible=icon]:hidden'>
              <span className='truncate text-[15px] font-semibold tracking-[0.12em] text-sidebar-foreground'>
                青灯不灭
              </span>
              <span className='mt-1 truncate text-[11px] text-sidebar-foreground/65'>
                观星辨势，藏卷养道
              </span>
            </div>
          </div>
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
