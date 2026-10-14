import { type SVGProps, useState } from 'react'
import { Root as Radio, Item } from '@radix-ui/react-radio-group'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { CircleCheck, Monitor, RotateCcw, Smartphone } from 'lucide-react'
import { IconDir } from '@/assets/custom/icon-dir'
import { IconLayoutCompact } from '@/assets/custom/icon-layout-compact'
import { IconLayoutDefault } from '@/assets/custom/icon-layout-default'
import { IconLayoutFull } from '@/assets/custom/icon-layout-full'
import { IconMobileBottomNav } from '@/assets/custom/icon-mobile-bottom-nav'
import { IconMobileSidebar } from '@/assets/custom/icon-mobile-sidebar'
import { IconSidebarFloating } from '@/assets/custom/icon-sidebar-floating'
import { IconSidebarSidebar } from '@/assets/custom/icon-sidebar-sidebar'
import { IconThemeDark } from '@/assets/custom/icon-theme-dark'
import { IconThemeLight } from '@/assets/custom/icon-theme-light'
import { IconThemeSystem } from '@/assets/custom/icon-theme-system'
import { getVersion } from '@/api/user.ts'
import { cn } from '@/lib/utils'
import { useDirection } from '@/context/direction-provider'
import {
  type Collapsible,
  type MobileNavigation,
  useLayout,
} from '@/context/layout-provider'
import { useTheme } from '@/context/theme-provider'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { useSidebar } from './ui/sidebar'

export function ConfigDrawer() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const navigate = useNavigate()
  const { setOpen } = useSidebar()
  const { resetDir } = useDirection()
  const { resetTheme } = useTheme()
  const { resetLayout } = useLayout()
  const isMobile = useIsMobile()

  const handleReset = () => {
    setOpen(true)
    resetDir()
    resetTheme()
    resetLayout()
  }

  const { data } = useQuery({
    queryKey: ['version'],
    queryFn: async () => {
      const res = await getVersion()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })
  const handleOpenUpdatePage = () => {
    setDrawerOpen(false)
    navigate({ to: '/settings/system' })
  }

  return (
    <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
      <SheetTrigger asChild>
        <Button
          size='icon'
          variant='ghost'
          aria-label='Open theme settings'
          aria-describedby='config-drawer-description'
          className='rounded-full'
        >
          {!isMobile && <Monitor aria-hidden='true' />}
          {isMobile && <Smartphone aria-hidden='true' />}
        </Button>
      </SheetTrigger>
      <SheetContent className='flex flex-col'>
        <SheetHeader className='pb-0 text-start'>
          <SheetTitle>主题设置</SheetTitle>
          <SheetDescription id='config-drawer-description'>
            根据喜好来调整布局、主题
          </SheetDescription>
        </SheetHeader>
        <div className='space-y-6 overflow-y-auto px-4'>
          <ThemeConfig />
          <MobileNavigationConfig />
          <SidebarConfig />
          <LayoutConfig />
          <DirConfig />
        </div>
        <SheetFooter className='gap-2'>
          <div className='mr-auto px-3 text-xs text-muted-foreground'>
            当前版本: {data}
          </div>
          <Button variant='outline' onClick={handleOpenUpdatePage}>
            检查更新
          </Button>
          <Button
            variant='destructive'
            onClick={handleReset}
            aria-label='Reset all settings to default values'
          >
            重置
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

function SectionTitle({
  title,
  showReset = false,
  onReset,
  className,
}: {
  title: string
  showReset?: boolean
  onReset?: () => void
  className?: string
}) {
  return (
    <div
      className={cn(
        'mb-2 flex items-center gap-2 text-sm font-semibold text-muted-foreground',
        className
      )}
    >
      {title}
      {showReset && onReset && (
        <Button
          size='icon'
          variant='secondary'
          className='size-4 rounded-full'
          onClick={onReset}
        >
          <RotateCcw className='size-3' />
        </Button>
      )}
    </div>
  )
}

function RadioGroupItem({
  item,
  isTheme = false,
}: {
  item: {
    value: string
    label: string
    icon: (props: SVGProps<SVGSVGElement>) => React.ReactElement
  }
  isTheme?: boolean
}) {
  return (
    <Item
      value={item.value}
      className={cn('group outline-none', 'transition duration-200 ease-in')}
      aria-label={`Select ${item.label.toLowerCase()}`}
      aria-describedby={`${item.value}-description`}
    >
      <div
        className={cn(
          'relative rounded-[6px] ring-[1px] ring-border',
          'group-data-[state=checked]:shadow-2xl group-data-[state=checked]:ring-primary',
          'group-focus-visible:ring-2'
        )}
        role='img'
        aria-hidden='false'
        aria-label={`${item.label} option preview`}
      >
        <CircleCheck
          className={cn(
            'size-6 fill-primary stroke-white',
            'group-data-[state=unchecked]:hidden',
            'absolute top-0 right-0 translate-x-1/2 -translate-y-1/2'
          )}
          aria-hidden='true'
        />
        <item.icon
          className={cn(
            !isTheme &&
              'fill-primary stroke-primary group-data-[state=unchecked]:fill-muted-foreground group-data-[state=unchecked]:stroke-muted-foreground'
          )}
          aria-hidden='true'
        />
      </div>
      <div
        className='mt-1 text-xs'
        id={`${item.value}-description`}
        aria-live='polite'
      >
        {item.label}
      </div>
    </Item>
  )
}

function ThemeConfig() {
  const { defaultTheme, theme, setTheme } = useTheme()
  return (
    <div>
      <SectionTitle
        title='主题'
        showReset={theme !== defaultTheme}
        onReset={() => setTheme(defaultTheme)}
      />
      <Radio
        value={theme}
        onValueChange={setTheme}
        className='grid w-full max-w-md grid-cols-3 gap-4'
        aria-label='Select theme preference'
        aria-describedby='theme-description'
      >
        {[
          {
            value: 'system',
            label: '系统',
            icon: IconThemeSystem,
          },
          {
            value: 'light',
            label: '明亮',
            icon: IconThemeLight,
          },
          {
            value: 'dark',
            label: '暗黑',
            icon: IconThemeDark,
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} isTheme />
        ))}
      </Radio>
      <div id='theme-description' className='sr-only'>
        选择根据系统、明亮、暗黑主题
      </div>
    </div>
  )
}

function MobileNavigationConfig() {
  const { defaultMobileNavigation, mobileNavigation, setMobileNavigation } =
    useLayout()

  return (
    <div className='md:hidden'>
      <SectionTitle
        title='移动导航'
        showReset={mobileNavigation !== defaultMobileNavigation}
        onReset={() => setMobileNavigation(defaultMobileNavigation)}
      />
      <Radio
        value={mobileNavigation}
        onValueChange={(value) =>
          setMobileNavigation(value as MobileNavigation)
        }
        className='grid w-full max-w-md grid-cols-2 gap-4'
        aria-label='Select mobile navigation style'
        aria-describedby='mobile-navigation-description'
      >
        {[
          {
            value: 'bottom-nav',
            label: '底部导航',
            icon: IconMobileBottomNav,
          },
          {
            value: 'sidebar',
            label: '侧边栏',
            icon: IconMobileSidebar,
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} />
        ))}
      </Radio>
      <div id='mobile-navigation-description' className='sr-only'>
        选择移动端使用底部导航还是侧边栏
      </div>
    </div>
  )
}

function SidebarConfig() {
  const { defaultVariant, variant, setVariant } = useLayout()
  return (
    <div className='max-md:hidden'>
      <SectionTitle
        title='侧边栏'
        showReset={defaultVariant !== variant}
        onReset={() => setVariant(defaultVariant)}
      />
      <Radio
        value={variant}
        onValueChange={setVariant}
        className='grid w-full max-w-md grid-cols-3 gap-4'
        aria-label='Select sidebar style'
        aria-describedby='sidebar-description'
      >
        {[
          {
            value: 'floating',
            label: '浮动式',
            icon: IconSidebarFloating,
          },
          {
            value: 'sidebar',
            label: '标准侧边栏',
            icon: IconSidebarSidebar,
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} />
        ))}
      </Radio>
      <div id='sidebar-description' className='sr-only'>
        在嵌入式、浮动式或标准侧边栏布局之间进行选择
      </div>
    </div>
  )
}

function LayoutConfig() {
  const { open, setOpen } = useSidebar()
  const { defaultCollapsible, collapsible, setCollapsible } = useLayout()

  const radioState = open ? 'default' : collapsible

  return (
    <div className='max-md:hidden'>
      <SectionTitle
        title='布局'
        showReset={radioState !== 'default'}
        onReset={() => {
          setOpen(true)
          setCollapsible(defaultCollapsible)
        }}
      />
      <Radio
        value={radioState}
        onValueChange={(v) => {
          if (v === 'default') {
            setOpen(true)
            return
          }
          setOpen(false)
          setCollapsible(v as Collapsible)
        }}
        className='grid w-full max-w-md grid-cols-3 gap-4'
        aria-label='Select layout style'
        aria-describedby='layout-description'
      >
        {[
          {
            value: 'default',
            label: '默认展开',
            icon: IconLayoutDefault,
          },
          {
            value: 'icon',
            label: '紧凑纯图标',
            icon: IconLayoutCompact,
          },
          {
            value: 'offcanvas',
            label: '完整布局',
            icon: IconLayoutFull,
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} />
        ))}
      </Radio>
      <div id='layout-description' className='sr-only'>
        在默认展开模式、紧凑纯图标模式或完整布局模式之间进行选择
      </div>
    </div>
  )
}

function DirConfig() {
  const { defaultDir, dir, setDir } = useDirection()
  return (
    <div className='max-md:hidden'>
      <SectionTitle
        title='排列'
        showReset={defaultDir !== dir}
        onReset={() => setDir(defaultDir)}
      />
      <Radio
        value={dir}
        onValueChange={setDir}
        className='grid w-full max-w-md grid-cols-3 gap-4'
        aria-label='Select site direction'
        aria-describedby='direction-description'
      >
        {[
          {
            value: 'ltr',
            label: '从左到右',
            icon: (props: SVGProps<SVGSVGElement>) => (
              <IconDir dir='ltr' {...props} />
            ),
          },
          {
            value: 'rtl',
            label: '从右到左',
            icon: (props: SVGProps<SVGSVGElement>) => (
              <IconDir dir='rtl' {...props} />
            ),
          },
        ].map((item) => (
          <RadioGroupItem key={item.value} item={item} />
        ))}
      </Radio>
      <div id='direction-description' className='sr-only'>
        选择从左到右或从右到左的布局方向
      </div>
    </div>
  )
}
