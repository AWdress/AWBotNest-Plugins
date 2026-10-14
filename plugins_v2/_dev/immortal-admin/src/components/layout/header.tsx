import * as React from 'react'
import { MoreHorizontal } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useLayout } from '@/context/layout-provider'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'

type HeaderProps = React.HTMLAttributes<HTMLElement> & {
  fixed?: boolean
  ref?: React.Ref<HTMLElement>
}

const MOBILE_PINNED_ACTION_NAMES = new Set([
  'ServerLogDialog',
  'ImageModeSwitch',
])

function getElementTypeName(type: unknown): string {
  if (!type || typeof type === 'string') return ''
  if (typeof type === 'function') {
    const functionType = type as { displayName?: string; name?: string }
    return functionType.displayName || functionType.name || ''
  }
  if (typeof type === 'object') {
    const elementType = type as {
      displayName?: string
      name?: string
      render?: { displayName?: string; name?: string }
      type?: { displayName?: string; name?: string }
    }
    return (
      elementType.displayName ||
      elementType.name ||
      elementType.render?.displayName ||
      elementType.render?.name ||
      elementType.type?.displayName ||
      elementType.type?.name ||
      ''
    )
  }
  return ''
}

export function Header({ className, fixed, children, ...props }: HeaderProps) {
  const [offset, setOffset] = React.useState(0)
  const isMobile = useIsMobile()
  const { mobileNavigation } = useLayout()
  const showSidebarTrigger = !isMobile || mobileNavigation === 'sidebar'

  React.useEffect(() => {
    const onScroll = () => {
      setOffset(document.body.scrollTop || document.documentElement.scrollTop)
    }

    document.addEventListener('scroll', onScroll, { passive: true })
    return () => document.removeEventListener('scroll', onScroll)
  }, [])

  const childArray = React.Children.toArray(children)
  const primaryChild = childArray[0] ?? null
  const overflowChildren = childArray.slice(1)
  const mobileActionItems = React.Children.toArray(
    overflowChildren.length === 1 &&
      React.isValidElement<{ children?: React.ReactNode }>(overflowChildren[0])
      ? overflowChildren[0].props.children
      : overflowChildren
  )
  const pinnedMobileActions = mobileActionItems.filter((item) => {
    if (!React.isValidElement(item)) return false
    return MOBILE_PINNED_ACTION_NAMES.has(getElementTypeName(item.type))
  })
  const menuMobileActions = mobileActionItems.filter((item) => {
    if (!React.isValidElement(item)) return true
    return !MOBILE_PINNED_ACTION_NAMES.has(getElementTypeName(item.type))
  })

  return (
    <header
      className={cn(
        'z-50',
        fixed && 'header-fixed peer/header sticky top-0 w-[inherit]',
        offset > 10 && fixed && 'bg-background/20 shadow backdrop-blur-lg',
        className
      )}
      {...props}
    >
      <div
        className={cn(
          'relative flex h-16 items-center gap-3 p-4 md:gap-4',
          offset > 10 &&
            fixed &&
            'after:absolute after:inset-0 after:-z-10 after:bg-background/20 after:backdrop-blur-lg'
        )}
      >
        {showSidebarTrigger && (
          <>
            <SidebarTrigger variant='outline' className='max-md:scale-125' />
            <Separator orientation='vertical' className='h-6' />
          </>
        )}

        {isMobile ? (
          <>
            <div className='min-w-0 flex-1'>{primaryChild}</div>
            <div className='flex shrink-0 items-center gap-1'>
              {pinnedMobileActions}
              {menuMobileActions.length > 0 && (
                <DropdownMenu modal={false}>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant='ghost'
                      size='icon'
                      className='shrink-0 rounded-full'
                      aria-label='打开更多工具'
                    >
                      <MoreHorizontal className='size-5' />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align='end'
                    side='bottom'
                    className='w-[min(20rem,calc(100vw-1rem))] bg-background/20 p-3 backdrop-blur-md'
                  >
                    <div className='flex flex-wrap justify-end gap-2'>
                      {menuMobileActions}
                    </div>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </>
        ) : (
          children
        )}
      </div>
    </header>
  )
}
