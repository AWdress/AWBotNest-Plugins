import { useEffect, useState } from 'react'
import { SlidersHorizontal } from 'lucide-react'
import { cn } from '@/lib/utils.ts'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog, DialogContent, DialogOverlay } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

interface ListOption {
  label: string
  value: string
}

export interface SiteOption {
  id: string
  name: string
  hasPeriod: boolean
  lists: ListOption[]
}

interface Period {
  id: string
  label: string
  icon: string
}

export type LibraryFilterValue = 'all' | 'in' | 'out'

interface LibraryOption {
  label: string
  value: LibraryFilterValue
}

export const RANK_MOVIE_SITES: SiteOption[] = [
  {
    id: 'library',
    name: '图书馆',
    hasPeriod: false,
    lists: [
      { label: '最想要', value: 'vl_mostwanted' },
      { label: '高评分', value: 'vl_bestrated' },
    ],
  },
  {
    id: 'javdb',
    name: 'JavDB',
    hasPeriod: true,
    lists: [
      { label: '有码', value: '0' },
      { label: '无码', value: '1' },
      { label: 'FC2', value: '3' },
    ],
  },
]

const PERIODS: Period[] = [
  { id: 'daily', label: '日榜', icon: '日' },
  { id: 'weekly', label: '周榜', icon: '周' },
  { id: 'monthly', label: '月榜', icon: '月' },
]

const LIBRARY_FILTERS: LibraryOption[] = [
  { label: '全部', value: 'all' },
  { label: '已入库', value: 'in' },
  { label: '未入库', value: 'out' },
]

export interface FilterValue {
  key: string
  site: SiteOption
  list: ListOption
  period: Period | null
  libraryFilter: LibraryFilterValue
}

interface FilterComponentProps {
  defaultSiteId?: string
  onApply: (value: FilterValue) => void
  showSiteTabs?: boolean
}

function buildKey(
  site: SiteOption,
  list: ListOption,
  period: Period | null
): string {
  const parts = [site.id, list.value]
  if (site.hasPeriod && period) parts.push(period.id)
  return parts.join('-')
}

interface SitePanelProps {
  site: SiteOption
  selectedList: ListOption
  selectedPeriod: Period | null
  selectedLibraryFilter: LibraryFilterValue
  onListChange: (list: ListOption) => void
  onPeriodChange: (period: Period) => void
  onLibraryFilterChange: (value: LibraryFilterValue) => void
}

function SitePanel({
  site,
  selectedList,
  selectedPeriod,
  selectedLibraryFilter,
  onListChange,
  onPeriodChange,
  onLibraryFilterChange,
}: SitePanelProps) {
  return (
    <div className='space-y-5'>
      <div className='space-y-2'>
        <p className='text-xs tracking-widest text-muted-foreground uppercase'>
          榜单类型
        </p>
        <div className='flex gap-2'>
          {site.lists.map((list) => (
            <Button
              key={list.value}
              size='sm'
              variant={
                selectedList.value === list.value ? 'default' : 'outline'
              }
              onClick={() => onListChange(list)}
              className='h-9 flex-1 gap-1.5 text-xs'
            >
              {list.label}
            </Button>
          ))}
        </div>
      </div>

      {site.hasPeriod && (
        <div className='space-y-2'>
          <p
            className={cn(
              'text-xs tracking-widest text-muted-foreground uppercase'
            )}
          >
            时间维度
          </p>
          <div className='flex gap-2'>
            {PERIODS.map((period) => (
              <Button
                key={period.id}
                size='sm'
                variant={
                  selectedPeriod?.id === period.id ? 'default' : 'outline'
                }
                onClick={() => onPeriodChange(period)}
                className='h-9 flex-1 gap-1.5 text-xs'
              >
                <span>{period.icon}</span>
                <span>{period.label}</span>
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className='space-y-2'>
        <p className='text-xs tracking-widest text-muted-foreground uppercase'>
          入库状态
        </p>
        <div className='flex gap-2'>
          {LIBRARY_FILTERS.map((option) => (
            <Button
              key={option.value}
              size='sm'
              variant={
                selectedLibraryFilter === option.value ? 'default' : 'outline'
              }
              onClick={() => onLibraryFilterChange(option.value)}
              className='h-9 flex-1 gap-1.5 text-xs'
            >
              {option.label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}

interface FilterContentProps {
  selectedSite: SiteOption
  selectedList: ListOption
  selectedPeriod: Period | null
  selectedLibraryFilter: LibraryFilterValue
  onSiteChange: (siteId: string) => void
  onListChange: (list: ListOption) => void
  onPeriodChange: (period: Period) => void
  onLibraryFilterChange: (value: LibraryFilterValue) => void
  showSiteTabs: boolean
}

function FilterContent({
  selectedSite,
  selectedList,
  selectedPeriod,
  selectedLibraryFilter,
  onSiteChange,
  onListChange,
  onPeriodChange,
  onLibraryFilterChange,
  showSiteTabs,
}: FilterContentProps) {
  if (!showSiteTabs) {
    return (
      <SitePanel
        site={selectedSite}
        selectedList={selectedList}
        selectedPeriod={selectedPeriod}
        selectedLibraryFilter={selectedLibraryFilter}
        onListChange={onListChange}
        onPeriodChange={onPeriodChange}
        onLibraryFilterChange={onLibraryFilterChange}
      />
    )
  }

  return (
    <Tabs value={selectedSite.id} onValueChange={onSiteChange}>
      <TabsList className='w-full' variant='line'>
        {RANK_MOVIE_SITES.map((site) => (
          <TabsTrigger key={site.id} value={site.id}>
            {site.name}
          </TabsTrigger>
        ))}
      </TabsList>

      {RANK_MOVIE_SITES.map((site) => (
        <TabsContent key={site.id} value={site.id} className='mt-0'>
          <SitePanel
            site={site}
            selectedList={selectedList}
            selectedPeriod={selectedPeriod}
            selectedLibraryFilter={selectedLibraryFilter}
            onListChange={onListChange}
            onPeriodChange={onPeriodChange}
            onLibraryFilterChange={onLibraryFilterChange}
          />
        </TabsContent>
      ))}
    </Tabs>
  )
}

interface RankFilterProps extends FilterComponentProps {
  isMobile?: boolean
}

export function RankFilter({
  defaultSiteId,
  onApply,
  isMobile,
  showSiteTabs = true,
}: RankFilterProps) {
  const resolveInitialSite = (siteId?: string) =>
    RANK_MOVIE_SITES.find((site) => site.id === siteId) ?? RANK_MOVIE_SITES[0]

  const initialSite = resolveInitialSite(defaultSiteId)

  const [selectedSite, setSelectedSite] = useState<SiteOption>(initialSite)
  const [selectedList, setSelectedList] = useState<ListOption>(
    initialSite.lists[0]
  )
  const [selectedPeriod, setSelectedPeriod] = useState<Period | null>(
    initialSite.hasPeriod ? PERIODS[0] : null
  )
  const [selectedLibraryFilter, setSelectedLibraryFilter] =
    useState<LibraryFilterValue>('all')
  const [dialogOpen, setDialogOpen] = useState(false)

  useEffect(() => {
    const site = resolveInitialSite(defaultSiteId)
    setSelectedSite(site)
    setSelectedList(site.lists[0])
    setSelectedPeriod(site.hasPeriod ? PERIODS[0] : null)
    setSelectedLibraryFilter('all')
    onApply({
      key: buildKey(site, site.lists[0], site.hasPeriod ? PERIODS[0] : null),
      site,
      list: site.lists[0],
      period: site.hasPeriod ? PERIODS[0] : null,
      libraryFilter: 'all',
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultSiteId])

  const emit = (
    site: SiteOption,
    list: ListOption,
    period: Period | null,
    libraryFilter: LibraryFilterValue
  ): void => {
    onApply({
      key: buildKey(site, list, period),
      site,
      list,
      period,
      libraryFilter,
    })
  }

  const handleSiteChange = (siteId: string): void => {
    const site = RANK_MOVIE_SITES.find((item) => item.id === siteId)
    if (!site) return
    const list = site.lists[0]
    const period = site.hasPeriod ? PERIODS[0] : null
    setSelectedSite(site)
    setSelectedList(list)
    setSelectedPeriod(period)
    emit(site, list, period, selectedLibraryFilter)
  }

  const handleListChange = (list: ListOption): void => {
    setSelectedList(list)
    emit(selectedSite, list, selectedPeriod, selectedLibraryFilter)
  }

  const handlePeriodChange = (period: Period): void => {
    setSelectedPeriod(period)
    emit(selectedSite, selectedList, period, selectedLibraryFilter)
  }

  const handleLibraryFilterChange = (value: LibraryFilterValue): void => {
    setSelectedLibraryFilter(value)
    emit(selectedSite, selectedList, selectedPeriod, value)
  }

  const contentProps: FilterContentProps = {
    selectedSite,
    selectedList,
    selectedPeriod,
    selectedLibraryFilter,
    onSiteChange: handleSiteChange,
    onListChange: handleListChange,
    onPeriodChange: handlePeriodChange,
    onLibraryFilterChange: handleLibraryFilterChange,
    showSiteTabs,
  }

  if (isMobile) {
    return (
      <>
        <Button
          size='icon'
          className='fixed right-4 bottom-[calc(6rem+env(safe-area-inset-bottom))] z-50 size-11 rounded-full shadow-lg'
          onClick={() => setDialogOpen(true)}
        >
          <SlidersHorizontal className='size-4' />
        </Button>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
          <DialogContent className='max-w-sm bg-background/40 backdrop-blur-lg'>
            <FilterContent {...contentProps} />
          </DialogContent>
        </Dialog>
      </>
    )
  }

  return (
    <Card className='pt-0 pb-2'>
      <CardContent className='px-0'>
        <FilterContent {...contentProps} />
      </CardContent>
    </Card>
  )
}
