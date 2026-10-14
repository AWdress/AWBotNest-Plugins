import { useEffect, useRef } from 'react'
import type { ArticleFilter, Section } from '@/api/article.ts'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface FilterBarProps {
  value: ArticleFilter
  categories: Section[]
  onChange: (v: ArticleFilter) => void
}

export function FilterBar({ value, categories, onChange }: FilterBarProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const tabsListRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!scrollAreaRef.current || !tabsListRef.current) return

    const scrollArea = scrollAreaRef.current
    const tabsList = tabsListRef.current
    const activeTab = tabsList.querySelector(
      '[data-state="active"]'
    ) as HTMLElement | null

    if (!activeTab) return

    const scrollContainer = scrollArea.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!scrollContainer) return

    const containerRect = scrollContainer.getBoundingClientRect()
    const activeRect = activeTab.getBoundingClientRect()
    const scrollLeft =
      activeTab.offsetLeft - containerRect.width / 2 + activeRect.width / 2

    scrollContainer.scrollTo({
      left: scrollLeft,
      behavior: 'smooth',
    })
  }, [value.section])

  return (
    <div className='relative w-full'>
      <ScrollArea
        ref={scrollAreaRef}
        className='mb-2 w-full'
        orientation='horizontal'
      >
        <Tabs
          value={value.section || 'all'}
          onValueChange={(v) =>
            onChange({ ...value, section: v === 'all' ? '' : v })
          }
        >
          <TabsList
            ref={tabsListRef}
            className='w-max min-w-full justify-start gap-2 bg-transparent p-0'
            variant='line'
          >
            <TabsTrigger
              value='all'
              className='rounded-xl border border-border/50 bg-background/35 px-3 py-1.5 text-foreground/72 transition-all data-[state=active]:border-amber-500/15 data-[state=active]:bg-amber-500/8 data-[state=active]:text-amber-700 dark:data-[state=active]:text-amber-300'
            >
              全部
            </TabsTrigger>
            {categories.map((c) => (
              <TabsTrigger
                key={c.name}
                value={c.name}
                className='rounded-xl border border-border/50 bg-background/35 px-3 py-1.5 text-foreground/72 transition-all data-[state=active]:border-amber-500/15 data-[state=active]:bg-amber-500/8 data-[state=active]:text-amber-700 dark:data-[state=active]:text-amber-300'
              >
                {c.name}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </ScrollArea>
    </div>
  )
}
