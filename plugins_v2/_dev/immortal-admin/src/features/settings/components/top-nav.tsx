import { type JSX } from 'react'
import { useLocation, useNavigate } from '@tanstack/react-router'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

type TopNavProps = React.HTMLAttributes<HTMLElement> & {
  items: {
    href: string
    title: string
    icon: JSX.Element
  }[]
}

export function TopNav({ items }: TopNavProps) {
  const { pathname } = useLocation()
  const navigate = useNavigate()

  const handleValueChange = (value: string) => {
    navigate({ to: value })
  }

  return (
    <ScrollArea orientation='horizontal' type='hover' className='w-full'>
      <Tabs
        value={pathname}
        onValueChange={handleValueChange}
        className='space-y-6'
      >
        <TabsList className='w-full gap-2 bg-transparent p-0' variant='line'>
          {items.map((item) => (
            <TabsTrigger
              key={item.href}
              value={item.href}
              className='group gap-2 rounded-2xl border border-border/60 bg-background/45 px-3 py-2 text-foreground/78 transition-all data-[state=active]:border-amber-500/20 data-[state=active]:bg-amber-500/10 data-[state=active]:text-amber-700 data-[state=active]:shadow-[0_10px_30px_rgba(245,158,11,0.08)] dark:data-[state=active]:text-amber-300'
            >
              <span className='me-1 flex size-8 items-center justify-center rounded-xl border border-emerald-500/12 bg-emerald-500/7 text-emerald-700 transition-all group-data-[state=active]:border-amber-500/25 group-data-[state=active]:bg-amber-500/12 group-data-[state=active]:text-amber-700 dark:text-emerald-300 dark:group-data-[state=active]:text-amber-300'>
                {item.icon}
              </span>
              {item.title}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </ScrollArea>
  )
}
