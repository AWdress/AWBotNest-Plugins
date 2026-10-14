'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Loader2,
  RefreshCw,
  Scroll,
  ShieldAlert,
  TriangleAlert,
  X,
} from 'lucide-react'
import { fetchLogs, type LogEntry } from '@/api/log.ts'
import { useUIStore } from '@/stores/ui-store.ts'
import { cn } from '@/lib/utils.ts'
import { useTheme } from '@/context/theme-provider.tsx'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS'

const LOG_LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'SUCCESS']
const PAGE_SIZE = 120

const levelMeta: Record<
  LogLevel,
  {
    label: string
    keyword: string
    badge: 'secondary' | 'default' | 'outline' | 'destructive'
    icon: typeof CircleDot
  }
> = {
  DEBUG: {
    label: '调试',
    keyword: 'DEBUG',
    badge: 'secondary',
    icon: CircleDot,
  },
  INFO: {
    label: '信息',
    keyword: 'INFO',
    badge: 'default',
    icon: CircleDot,
  },
  WARN: {
    label: '警告',
    keyword: 'WARN',
    badge: 'outline',
    icon: TriangleAlert,
  },
  ERROR: {
    label: '错误',
    keyword: 'ERROR',
    badge: 'destructive',
    icon: ShieldAlert,
  },
  SUCCESS: {
    label: '成功',
    keyword: 'SUCCESS',
    badge: 'secondary',
    icon: CheckCircle2,
  },
}

function detectLogLevel(line: string): LogLevel | null {
  for (const level of LOG_LEVELS) {
    if (line.includes(levelMeta[level].keyword)) {
      return level
    }
  }
  return null
}

function extractTimestamp(line: string): string {
  const match = line.match(
    /\d{4}-\d{2}-\d{2}[^\s]*\s+\d{2}:\d{2}:\d{2}(?:,\d{3})?/
  )
  return match?.[0] ?? ''
}

function mergeLogEntries(current: LogEntry[], incoming: LogEntry[]) {
  const merged = new Map<number, LogEntry>()
  for (const item of current) merged.set(item.line_no, item)
  for (const item of incoming) merged.set(item.line_no, item)
  return Array.from(merged.values()).sort((a, b) => a.line_no - b.line_no)
}

function getLevelTone(
  level: LogLevel,
  resolvedTheme: 'light' | 'dark',
  active: boolean
) {
  const palette = {
    DEBUG:
      resolvedTheme === 'dark'
        ? 'border-slate-700 bg-slate-900/70 text-slate-200'
        : 'border-slate-200 bg-slate-100/90 text-slate-700',
    INFO:
      resolvedTheme === 'dark'
        ? 'border-sky-900 bg-sky-950/70 text-sky-200'
        : 'border-sky-200 bg-sky-50 text-sky-700',
    WARN:
      resolvedTheme === 'dark'
        ? 'border-amber-900 bg-amber-950/70 text-amber-200'
        : 'border-amber-200 bg-amber-50 text-amber-700',
    ERROR:
      resolvedTheme === 'dark'
        ? 'border-rose-900 bg-rose-950/70 text-rose-200'
        : 'border-rose-200 bg-rose-50 text-rose-700',
    SUCCESS:
      resolvedTheme === 'dark'
        ? 'border-emerald-900 bg-emerald-950/70 text-emerald-200'
        : 'border-emerald-200 bg-emerald-50 text-emerald-700',
  } satisfies Record<LogLevel, string>

  if (active) {
    return palette[level]
  }

  return resolvedTheme === 'dark'
    ? 'border-border/60 bg-background/50 text-muted-foreground hover:bg-accent/50 hover:text-foreground'
    : 'border-border/80 bg-muted/30 text-muted-foreground hover:bg-accent hover:text-foreground'
}

export function ServerLogDialog() {
  const [open, setOpen] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const [selectedLevels, setSelectedLevels] = useState<LogLevel[]>(LOG_LEVELS)
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isLoadingOlder, setIsLoadingOlder] = useState(false)
  const [hasMoreBefore, setHasMoreBefore] = useState(false)
  const [totalLines, setTotalLines] = useState(0)
  const [controlsCollapsed, setControlsCollapsed] = useState(false)

  const touchStartY = useRef(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const autoScrollRef = useRef(true)
  const latestLineNoRef = useRef<number | null>(null)
  const oldestLineNoRef = useRef<number | null>(null)
  const hasMoreBeforeRef = useRef(false)
  const isLoadingOlderRef = useRef(false)

  const setHideBottomNav = useUIStore((s) => s.setHideBottomNav)
  const isMobile = useIsMobile()
  const { resolvedTheme } = useTheme()
  const dialogHistoryActiveRef = useRef(false)
  const closingFromPopStateRef = useRef(false)

  useEffect(() => {
    setHideBottomNav(open)
    return () => setHideBottomNav(false)
  }, [open, setHideBottomNav])

  useEffect(() => {
    if (!open) return
    setControlsCollapsed(isMobile)
  }, [open, isMobile])

  useEffect(() => {
    hasMoreBeforeRef.current = hasMoreBefore
  }, [hasMoreBefore])

  useEffect(() => {
    isLoadingOlderRef.current = isLoadingOlder
  }, [isLoadingOlder])

  useEffect(() => {
    latestLineNoRef.current =
      logEntries.length > 0 ? logEntries[logEntries.length - 1].line_no : null
    oldestLineNoRef.current = logEntries[0]?.line_no ?? null
  }, [logEntries])

  useEffect(() => {
    if (!open || !isMobile) return

    closingFromPopStateRef.current = false
    dialogHistoryActiveRef.current = true
    window.history.pushState({ __serverLogDialog: true }, '')

    const handlePopState = () => {
      if (!dialogHistoryActiveRef.current) return
      dialogHistoryActiveRef.current = false
      closingFromPopStateRef.current = true
      setOpen(false)
    }

    window.addEventListener('popstate', handlePopState)

    return () => {
      window.removeEventListener('popstate', handlePopState)
      if (dialogHistoryActiveRef.current) {
        dialogHistoryActiveRef.current = false
        if (!closingFromPopStateRef.current) {
          window.history.back()
        }
      }
      closingFromPopStateRef.current = false
    }
  }, [open, isMobile])

  const setAutoScrollBoth = (value: boolean) => {
    autoScrollRef.current = value
    setAutoScroll(value)
  }

  const loadLatestLogs = useCallback(async (reset = false) => {
    setIsRefreshing(true)
    try {
      const response = await fetchLogs({ page_size: PAGE_SIZE })
      const page = response.data
      setLogEntries(page.items)
      setTotalLines(page.total_lines)
      setHasMoreBefore(page.has_more_before)
      if (reset) {
        setAutoScrollBoth(true)
      }
    } finally {
      setIsRefreshing(false)
    }
  }, [])

  const refreshLogs = useCallback(async () => {
    const latestLineNo = latestLineNoRef.current
    if (!latestLineNo) {
      await loadLatestLogs(true)
      return
    }

    setIsRefreshing(true)
    try {
      const response = await fetchLogs({
        page_size: PAGE_SIZE,
        after_line_no: latestLineNo,
      })
      const page = response.data
      setTotalLines(page.total_lines)
      if (page.items.length > 0) {
        setLogEntries((prev) => mergeLogEntries(prev, page.items))
      }
    } finally {
      setIsRefreshing(false)
    }
  }, [loadLatestLogs])

  const loadOlderLogs = useCallback(async () => {
    const oldestLineNo = oldestLineNoRef.current
    const el = scrollRef.current
    if (
      !oldestLineNo ||
      !el ||
      isLoadingOlderRef.current ||
      !hasMoreBeforeRef.current
    )
      return

    setIsLoadingOlder(true)
    const previousHeight = el.scrollHeight
    const previousTop = el.scrollTop

    try {
      const response = await fetchLogs({
        page_size: PAGE_SIZE,
        before_line_no: oldestLineNo,
      })
      const page = response.data
      setTotalLines(page.total_lines)
      setHasMoreBefore(page.has_more_before)
      if (page.items.length > 0) {
        setLogEntries((prev) => mergeLogEntries(prev, page.items))
        requestAnimationFrame(() => {
          const nextEl = scrollRef.current
          if (!nextEl) return
          nextEl.scrollTop = nextEl.scrollHeight - previousHeight + previousTop
        })
      }
    } finally {
      setIsLoadingOlder(false)
    }
  }, [])

  useEffect(() => {
    if (!open) return

    void loadLatestLogs(true)
    const timer = setInterval(() => {
      void refreshLogs()
    }, 5000)
    return () => clearInterval(timer)
  }, [open, loadLatestLogs, refreshLogs])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return

    const handleScroll = () => {
      const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
      if (!autoScrollRef.current && distanceToBottom < 48) {
        setAutoScrollBoth(true)
      }
      if (el.scrollTop < 80) {
        void loadOlderLogs()
      }
    }

    el.addEventListener('scroll', handleScroll)
    return () => el.removeEventListener('scroll', handleScroll)
  }, [loadOlderLogs])

  const filteredLogs = useMemo(() => {
    return logEntries.filter((entry) => {
      const level = detectLogLevel(entry.text)
      if (!level) return true
      return selectedLevels.includes(level)
    })
  }, [logEntries, selectedLevels])

  useEffect(() => {
    const el = scrollRef.current
    if (!el || !autoScrollRef.current) return
    el.scrollTop = el.scrollHeight
  }, [filteredLogs])

  const levelCounts = useMemo(() => {
    return LOG_LEVELS.reduce<Record<LogLevel, number>>(
      (acc, level) => {
        acc[level] = logEntries.filter((entry) =>
          entry.text.includes(levelMeta[level].keyword)
        ).length
        return acc
      },
      { DEBUG: 0, INFO: 0, WARN: 0, ERROR: 0, SUCCESS: 0 }
    )
  }, [logEntries])

  const latestTimestamp = useMemo(() => {
    for (let index = filteredLogs.length - 1; index >= 0; index -= 1) {
      const timestamp = extractTimestamp(filteredLogs[index].text)
      if (timestamp) return timestamp
    }
    return ''
  }, [filteredLogs])

  const toggleLevel = (level: LogLevel) => {
    setSelectedLevels((prev) =>
      prev.includes(level)
        ? prev.filter((item) => item !== level)
        : [...prev, level]
    )
  }

  const enableAllLevels = () => setSelectedLevels(LOG_LEVELS)

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => setOpen(nextOpen)}>
      <DialogOverlay className='bg-background/55 backdrop-blur-md' />
      <DialogTrigger asChild>
        <Button variant='ghost' size='icon' className='rounded-full'>
          <Scroll className='h-5 w-5' />
        </Button>
      </DialogTrigger>

      <DialogContent
        showCloseButton={false}
        className='flex min-h-0 max-w-none flex-col gap-0 overflow-hidden border-border/60 bg-background/96 p-0 text-foreground shadow-2xl sm:max-w-none md:h-[86vh] md:w-[min(1120px,92vw)] md:max-w-none md:rounded-3xl'
      >
        <DialogHeader className='border-b border-border/60 bg-linear-to-br from-background via-background to-muted/40 px-4 py-4 text-left md:px-6'>
          <div className='flex items-start justify-between gap-4'>
            <div className='space-y-2'>
              <div className='flex items-center gap-2'>
                <div className='rounded-2xl border border-primary/20 bg-primary/10 p-2 text-primary'>
                  <Scroll className='h-5 w-5' />
                </div>
                <div>
                  <DialogTitle className='text-base font-semibold tracking-wide text-foreground md:text-lg'>
                    服务日志
                  </DialogTitle>
                </div>
              </div>
              <div className='flex flex-wrap gap-2'>
                <Badge
                  variant='secondary'
                  className='border border-border/60 bg-muted/40 text-foreground'
                >
                  总计 {totalLines} 行
                </Badge>
                <Badge
                  variant='secondary'
                  className='border border-border/60 bg-muted/40 text-foreground'
                >
                  当前已加载 {logEntries.length} 行
                </Badge>
                <Badge
                  variant='secondary'
                  className={cn(
                    'border',
                    autoScroll
                      ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300'
                      : 'border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300'
                  )}
                >
                  {autoScroll ? '自动追踪已开启' : '自动追踪已暂停'}
                </Badge>
                {latestTimestamp && (
                  <Badge
                    variant='outline'
                    className='border-border/60 bg-transparent text-muted-foreground'
                  >
                    最近时间 {latestTimestamp}
                  </Badge>
                )}
              </div>
            </div>
            <div className='flex items-center gap-2'>
              <Button
                variant='outline'
                size='icon'
                onClick={() => void refreshLogs()}
                className='rounded-full border-border/60 bg-background/70 text-foreground hover:bg-muted'
                disabled={isRefreshing}
                aria-label='刷新日志'
              >
                <RefreshCw
                  className={cn('h-4 w-4', isRefreshing && 'animate-spin')}
                />
              </Button>
              <Button
                size='icon'
                variant='ghost'
                onClick={() => setOpen(false)}
                className='rounded-full text-foreground hover:bg-muted'
                aria-label='关闭日志弹窗'
              >
                <X className='h-5 w-5' />
              </Button>
            </div>
          </div>
        </DialogHeader>

        <div className='grid min-h-0 flex-1 gap-0 md:grid-cols-[300px_minmax(0,1fr)]'>
          {isMobile ? (
            <Collapsible
              open={!controlsCollapsed}
              onOpenChange={(nextOpen) => setControlsCollapsed(!nextOpen)}
              className='border-b border-border/60'
            >
              <div className='bg-muted/20 px-4 py-3'>
                <CollapsibleTrigger asChild>
                  <Button
                    variant='ghost'
                    className='flex w-full items-center justify-between rounded-2xl px-3 py-5 text-left'
                  >
                    <div>
                      <div className='text-sm font-medium text-foreground'>
                        控制台
                      </div>
                    </div>
                    <ChevronDown
                      className={cn(
                        'h-4 w-4 transition-transform',
                        !controlsCollapsed && 'rotate-180'
                      )}
                    />
                  </Button>
                </CollapsibleTrigger>
              </div>
              <CollapsibleContent className='border-t border-border/50 bg-muted/15'>
                <aside className='p-4'>
                  <div className='space-y-4'>
                    <div className='space-y-2'>
                      <div className='text-xs font-semibold tracking-[0.2em] text-muted-foreground uppercase'>
                        过滤等级
                      </div>
                      <div className='grid grid-cols-2 gap-2'>
                        {LOG_LEVELS.map((level) => {
                          const meta = levelMeta[level]
                          const Icon = meta.icon
                          const active = selectedLevels.includes(level)
                          const countBadgeTone = !active
                            ? resolvedTheme === 'dark'
                              ? 'border-border/60 bg-background/70 text-muted-foreground'
                              : 'border-border/70 bg-background/80 text-muted-foreground'
                            : {
                                DEBUG:
                                  resolvedTheme === 'dark'
                                    ? 'border-slate-700/80 bg-slate-200 text-slate-950'
                                    : 'border-slate-200 bg-slate-700 text-slate-50',
                                INFO:
                                  resolvedTheme === 'dark'
                                    ? 'border-sky-700/80 bg-sky-200 text-sky-950'
                                    : 'border-sky-200 bg-sky-700 text-sky-50',
                                WARN:
                                  resolvedTheme === 'dark'
                                    ? 'border-amber-700/80 bg-amber-200 text-amber-950'
                                    : 'border-amber-200 bg-amber-700 text-amber-50',
                                ERROR:
                                  resolvedTheme === 'dark'
                                    ? 'border-rose-700/80 bg-rose-200 text-rose-950'
                                    : 'border-rose-200 bg-rose-700 text-rose-50',
                                SUCCESS:
                                  resolvedTheme === 'dark'
                                    ? 'border-emerald-700/80 bg-emerald-200 text-emerald-950'
                                    : 'border-emerald-200 bg-emerald-700 text-emerald-50',
                              }[level]
                          return (
                            <button
                              key={level}
                              type='button'
                              onClick={() => toggleLevel(level)}
                              className={cn(
                                'flex items-center justify-between rounded-2xl border px-3 py-2.5 text-left transition-all',
                                getLevelTone(level, resolvedTheme, active)
                              )}
                            >
                              <span className='flex items-center gap-2'>
                                <Icon className='h-4 w-4' />
                                <span className='text-sm font-medium'>
                                  {level}
                                </span>
                              </span>
                              <Badge
                                variant='outline'
                                className={cn(
                                  'min-w-9 justify-center border font-semibold tabular-nums',
                                  countBadgeTone
                                )}
                              >
                                {levelCounts[level]}
                              </Badge>
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <div className='rounded-2xl border border-border/60 bg-background/70 p-3'>
                      <div className='mb-3 text-xs font-semibold tracking-[0.2em] text-muted-foreground uppercase'>
                        控制
                      </div>
                      <div className='flex flex-wrap gap-2'>
                        <Button
                          variant={autoScroll ? 'default' : 'outline'}
                          onClick={() => setAutoScrollBoth(!autoScroll)}
                          className={cn(
                            'rounded-xl',
                            autoScroll
                              ? 'bg-emerald-600 text-white hover:bg-emerald-600/90'
                              : 'border-border/60 bg-transparent text-foreground hover:bg-muted'
                          )}
                        >
                          {autoScroll ? '关闭自动追踪' : '开启自动追踪'}
                        </Button>
                        <Button
                          variant='outline'
                          onClick={enableAllLevels}
                          className='rounded-xl border-border/60 bg-transparent text-foreground hover:bg-muted'
                        >
                          全部显示
                        </Button>
                      </div>
                    </div>
                  </div>
                </aside>
              </CollapsibleContent>
            </Collapsible>
          ) : (
            <aside className='border-r border-border/60 bg-muted/15 p-5'>
              <div className='space-y-4'>
                <div className='space-y-2'>
                  <div className='text-xs font-semibold tracking-[0.2em] text-muted-foreground uppercase'>
                    过滤等级
                  </div>
                  <div className='grid grid-cols-1 gap-2'>
                    {LOG_LEVELS.map((level) => {
                      const meta = levelMeta[level]
                      const Icon = meta.icon
                      const active = selectedLevels.includes(level)
                      const countBadgeTone = !active
                        ? resolvedTheme === 'dark'
                          ? 'border-border/60 bg-background/70 text-muted-foreground'
                          : 'border-border/70 bg-background/80 text-muted-foreground'
                        : {
                            DEBUG:
                              resolvedTheme === 'dark'
                                ? 'border-slate-700/80 bg-slate-200 text-slate-950'
                                : 'border-slate-200 bg-slate-700 text-slate-50',
                            INFO:
                              resolvedTheme === 'dark'
                                ? 'border-sky-700/80 bg-sky-200 text-sky-950'
                                : 'border-sky-200 bg-sky-700 text-sky-50',
                            WARN:
                              resolvedTheme === 'dark'
                                ? 'border-amber-700/80 bg-amber-200 text-amber-950'
                                : 'border-amber-200 bg-amber-700 text-amber-50',
                            ERROR:
                              resolvedTheme === 'dark'
                                ? 'border-rose-700/80 bg-rose-200 text-rose-950'
                                : 'border-rose-200 bg-rose-700 text-rose-50',
                            SUCCESS:
                              resolvedTheme === 'dark'
                                ? 'border-emerald-700/80 bg-emerald-200 text-emerald-950'
                                : 'border-emerald-200 bg-emerald-700 text-emerald-50',
                          }[level]
                      return (
                        <button
                          key={level}
                          type='button'
                          onClick={() => toggleLevel(level)}
                          className={cn(
                            'flex items-center justify-between rounded-2xl border px-3 py-2.5 text-left transition-all',
                            getLevelTone(level, resolvedTheme, active)
                          )}
                        >
                          <span className='flex items-center gap-2'>
                            <Icon className='h-4 w-4' />
                            <span className='text-sm font-medium'>{level}</span>
                            <span className='text-xs opacity-80'>
                              {meta.label}
                            </span>
                          </span>
                          <Badge
                            variant='outline'
                            className={cn(
                              'min-w-9 justify-center border font-semibold tabular-nums',
                              countBadgeTone
                            )}
                          >
                            {levelCounts[level]}
                          </Badge>
                        </button>
                      )
                    })}
                  </div>
                </div>

                <div className='rounded-2xl border border-border/60 bg-background/70 p-3'>
                  <div className='mb-3 text-xs font-semibold tracking-[0.2em] text-muted-foreground uppercase'>
                    控制
                  </div>
                  <div className='flex flex-wrap gap-2'>
                    <Button
                      variant={autoScroll ? 'default' : 'outline'}
                      onClick={() => setAutoScrollBoth(!autoScroll)}
                      className={cn(
                        'rounded-xl',
                        autoScroll
                          ? 'bg-emerald-600 text-white hover:bg-emerald-600/90'
                          : 'border-border/60 bg-transparent text-foreground hover:bg-muted'
                      )}
                    >
                      {autoScroll ? '关闭自动追踪' : '开启自动追踪'}
                    </Button>
                    <Button
                      variant='outline'
                      onClick={enableAllLevels}
                      className='rounded-xl border-border/60 bg-transparent text-foreground hover:bg-muted'
                    >
                      全部显示
                    </Button>
                  </div>
                </div>
              </div>
            </aside>
          )}

          <section className='min-h-0 bg-linear-to-b from-background to-muted/20 p-3 md:p-5'>
            <div className='flex h-full min-h-0 flex-col overflow-hidden rounded-3xl border border-border/60 bg-background/85 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'>
              <div
                ref={scrollRef}
                onWheel={(event) => {
                  if (event.deltaY < 0) {
                    setAutoScrollBoth(false)
                  }
                }}
                onTouchStart={(event) => {
                  touchStartY.current = event.touches[0].clientY
                }}
                onTouchMove={(event) => {
                  const delta = event.touches[0].clientY - touchStartY.current
                  if (delta > 0) {
                    setAutoScrollBoth(false)
                  }
                }}
                className='scrollbar-hide min-h-0 flex-1 overflow-y-auto px-3 py-3 md:px-4'
              >
                <div className='space-y-2'>
                  {(hasMoreBefore || isLoadingOlder) && (
                    <div className='flex justify-center pb-1'>
                      <Button
                        variant='outline'
                        onClick={() => void loadOlderLogs()}
                        disabled={isLoadingOlder}
                        className='rounded-full border-border/60 bg-background/70 text-foreground hover:bg-muted'
                      >
                        {isLoadingOlder ? (
                          <>
                            <Loader2 className='mr-2 h-4 w-4 animate-spin' />
                            加载更早日志
                          </>
                        ) : (
                          '加载更早日志'
                        )}
                      </Button>
                    </div>
                  )}

                  {filteredLogs.length === 0 ? (
                    <div className='flex min-h-60 items-center justify-center rounded-2xl border border-dashed border-border/60 bg-muted/20 p-6 text-center text-sm text-muted-foreground'>
                      当前没有匹配的日志，试试调整等级筛选。
                    </div>
                  ) : (
                    filteredLogs.map((entry) => {
                      const level = detectLogLevel(entry.text)
                      const timestamp = extractTimestamp(entry.text)
                      const message = timestamp
                        ? entry.text.replace(timestamp, '').trim()
                        : entry.text
                      const toneClass = level
                        ? getLevelTone(level, resolvedTheme, true)
                        : resolvedTheme === 'dark'
                          ? 'border-border/60 bg-background/50 text-foreground'
                          : 'border-border/70 bg-muted/20 text-foreground'

                      return (
                        <div
                          key={entry.line_no}
                          className={cn(
                            'group rounded-2xl border px-3 py-2.5 transition-colors hover:bg-accent/40',
                            toneClass
                          )}
                        >
                          <div className='flex items-start gap-3'>
                            <div className='mt-0.5 flex min-w-0 flex-1 flex-col gap-1'>
                              <div className='flex flex-wrap items-center gap-2 text-xs'>
                                <span className='rounded-full border border-border/60 bg-background/80 px-2 py-0.5 font-mono text-muted-foreground'>
                                  #{entry.line_no}
                                </span>
                                {level && (
                                  <Badge
                                    variant='outline'
                                    className='border-border/60 bg-background/70 text-inherit'
                                  >
                                    {level}
                                  </Badge>
                                )}
                                {timestamp && (
                                  <span className='font-mono text-muted-foreground'>
                                    {timestamp}
                                  </span>
                                )}
                              </div>
                              <pre className='overflow-x-auto font-mono text-[12px] leading-5 break-all whitespace-pre-wrap text-inherit'>
                                {message || entry.text}
                              </pre>
                            </div>
                          </div>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
