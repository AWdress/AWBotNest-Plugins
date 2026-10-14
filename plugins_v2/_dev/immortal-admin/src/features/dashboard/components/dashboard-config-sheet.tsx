import { useEffect, useMemo, useState, type TouchEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { GripVertical, LayoutPanelTop, RotateCcw, Save } from 'lucide-react'
import { toast } from 'sonner'
import { getConfig, postConfig } from '@/api/config.ts'
import { Button } from '@/components/ui/button.tsx'
import { Checkbox } from '@/components/ui/checkbox.tsx'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet.tsx'
import { cn } from '@/lib/utils.ts'
import {
  DASHBOARD_CONFIG_KEY,
  DASHBOARD_CONFIG_QUERY_KEY,
  DASHBOARD_SECTION_DEFINITIONS,
  DEFAULT_DASHBOARD_SECTIONS,
  resolveDashboardSections,
  type DashboardConfigPayload,
  type DashboardSectionKey,
} from '@/features/dashboard/dashboard-config.ts'

export function DashboardConfigSheet() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [selectedSections, setSelectedSections] = useState<DashboardSectionKey[]>(
    DEFAULT_DASHBOARD_SECTIONS
  )
  const [draggingKey, setDraggingKey] = useState<DashboardSectionKey | null>(null)
  const [dragOverKey, setDragOverKey] = useState<DashboardSectionKey | null>(null)

  const { data } = useQuery({
    queryKey: DASHBOARD_CONFIG_QUERY_KEY,
    queryFn: async () => {
      const res = await getConfig<DashboardConfigPayload>(DASHBOARD_CONFIG_KEY)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const currentSections = useMemo(() => resolveDashboardSections(data), [data])

  const orderedSections = useMemo(() => {
    const selected = new Set(selectedSections)
    const selectedRows = selectedSections.reduce<
      (typeof DASHBOARD_SECTION_DEFINITIONS)[number][]
    >((items, key) => {
      const section = DASHBOARD_SECTION_DEFINITIONS.find((item) => item.key === key)
      if (section) {
        items.push(section)
      }
      return items
    }, [])
    const unselectedRows = DASHBOARD_SECTION_DEFINITIONS.filter(
      (item) => !selected.has(item.key)
    )
    return [...selectedRows, ...unselectedRows]
  }, [selectedSections])

  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedSections(currentSections)
    }
  }, [currentSections, open])

  const handleToggle = (key: DashboardSectionKey, checked: boolean) => {
    setSelectedSections((current) => {
      if (checked) {
        if (current.includes(key)) {
          return current
        }
        return [...current, key]
      }
      return current.filter((item) => item !== key)
    })
  }

  const moveSection = (sourceKey: DashboardSectionKey, targetKey: DashboardSectionKey) => {
    setSelectedSections((current) => {
      const fromIndex = current.indexOf(sourceKey)
      const toIndex = current.indexOf(targetKey)
      if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) {
        return current
      }
      const next = [...current]
      const [moved] = next.splice(fromIndex, 1)
      next.splice(toIndex, 0, moved)
      return next
    })
  }

  const handleDragStart = (key: DashboardSectionKey) => {
    setDraggingKey(key)
    setDragOverKey(key)
  }

  const handleDragEnter = (targetKey: DashboardSectionKey) => {
    if (!draggingKey || draggingKey === targetKey) {
      return
    }
    moveSection(draggingKey, targetKey)
    setDragOverKey(targetKey)
  }

  const handleDragEnd = () => {
    setDraggingKey(null)
    setDragOverKey(null)
  }

  const handleTouchStart = (key: DashboardSectionKey) => (event: TouchEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    setDraggingKey(key)
    setDragOverKey(key)
  }

  const handleTouchMove = (event: TouchEvent<HTMLButtonElement>) => {
    if (!draggingKey) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    const touch = event.touches[0]
    if (!touch) {
      return
    }
    const targetElement = document
      .elementFromPoint(touch.clientX, touch.clientY)
      ?.closest<HTMLElement>('[data-dashboard-section-key]')
    const targetKey = targetElement?.dataset.dashboardSectionKey as
      | DashboardSectionKey
      | undefined
    if (!targetKey || targetKey === draggingKey || !selectedSections.includes(targetKey)) {
      return
    }
    moveSection(draggingKey, targetKey)
    setDragOverKey(targetKey)
  }

  const handleTouchEnd = (event: TouchEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    handleDragEnd()
  }

  const handleSave = async () => {
    const payload: DashboardConfigPayload = { sections: selectedSections }
    const res = await postConfig(DASHBOARD_CONFIG_KEY, payload as never)
    queryClient.invalidateQueries({
      queryKey: DASHBOARD_CONFIG_QUERY_KEY,
      exact: true,
    })
    toast.success(res.message || '首页配置已保存')
    setOpen(false)
  }

  const handleReset = () => {
    setSelectedSections(DEFAULT_DASHBOARD_SECTIONS)
    setDraggingKey(null)
    setDragOverKey(null)
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant='ghost' size='icon' title='编辑首页'>
          <LayoutPanelTop className='h-4 w-4' />
        </Button>
      </SheetTrigger>
      <SheetContent className='flex flex-col gap-0 sm:max-w-xl'>
        <SheetHeader className='text-left'>
          <SheetTitle>首页组件</SheetTitle>
          <SheetDescription>
            选择首页要展示的模块。已启用模块可通过拖拽手柄调整展示顺序。
          </SheetDescription>
        </SheetHeader>

        <div className='flex-1 space-y-3 overflow-y-auto px-4 py-6'>
          {orderedSections.map((section) => {
            const checked = selectedSections.includes(section.key)
            const selectedIndex = selectedSections.indexOf(section.key)
            const isDragging = draggingKey === section.key
            const isDragTarget = dragOverKey === section.key && draggingKey !== section.key

            return (
              <label
                key={section.key}
                data-dashboard-section-key={section.key}
                draggable={checked}
                onDragStart={() => checked && handleDragStart(section.key)}
                onDragEnter={() => checked && draggingKey && handleDragEnter(section.key)}
                onDragOver={(event) => {
                  if (!checked || !draggingKey) return
                  event.preventDefault()
                }}
                onDrop={(event) => {
                  event.preventDefault()
                  handleDragEnd()
                }}
                onDragEnd={handleDragEnd}
                className={cn(
                  'flex cursor-pointer items-start gap-3 rounded-2xl border border-border/70 bg-background/60 px-4 py-3 transition-colors hover:border-primary/40 hover:bg-primary/5',
                  checked && 'cursor-grab',
                  isDragging && 'opacity-55',
                  isDragTarget && 'border-primary bg-primary/8'
                )}
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={(value) =>
                    handleToggle(section.key, value === true)
                  }
                  className='mt-1'
                />
                <div className='min-w-0 flex-1'>
                  <div className='flex items-start justify-between gap-3'>
                    <div className='min-w-0'>
                      <div className='text-sm font-medium'>{section.title}</div>
                      <div className='mt-1 text-xs text-muted-foreground'>
                        {section.description}
                      </div>
                      {checked && (
                        <div className='mt-2 text-xs text-primary'>
                          当前顺序：第 {selectedIndex + 1} 位
                        </div>
                      )}
                    </div>
                    {checked && (
                      <button
                        type='button'
                        aria-label={`拖拽排序 ${section.title}`}
                        onClick={(event) => {
                          event.preventDefault()
                          event.stopPropagation()
                        }}
                        onTouchStart={handleTouchStart(section.key)}
                        onTouchMove={handleTouchMove}
                        onTouchEnd={handleTouchEnd}
                        onTouchCancel={handleTouchEnd}
                        className='flex shrink-0 touch-none items-center gap-2 rounded-full border border-border/70 bg-background/70 px-2 py-1 text-xs text-muted-foreground'
                      >
                        <GripVertical className='h-4 w-4' />
                        拖拽排序
                      </button>
                    )}
                  </div>
                </div>
              </label>
            )
          })}
        </div>

        <SheetFooter className='gap-2 border-t px-4 py-4 sm:justify-between'>
          <Button variant='ghost' onClick={handleReset} className='gap-2'>
            <RotateCcw className='h-4 w-4' />
            恢复默认
          </Button>
          <Button onClick={handleSave} className='gap-2'>
            <Save className='h-4 w-4' />
            保存首页配置
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
