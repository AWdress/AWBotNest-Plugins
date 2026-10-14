import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Mountain } from 'lucide-react'
import { flattenSectionTotals, getCategories } from '@/api/article.ts'
import { getConfig } from '@/api/config.ts'
import { getDownloadState } from '@/api/download-log.ts'
import { Card, CardContent } from '@/components/ui/card.tsx'
import { ConfigDrawer } from '@/components/config-drawer'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch'
import { useUIStore } from '@/stores/ui-store'
import { CategoryCards } from '@/features/dashboard/components/category-cards.tsx'
import { DashboardConfigSheet } from '@/features/dashboard/components/dashboard-config-sheet.tsx'
import { DownloadDashboard } from '@/features/dashboard/components/download-state.tsx'
import { MovieFrequencyStatsPanel } from '@/features/dashboard/components/movie-frequency-stats.tsx'
import { SubscriptionRecommendations } from '@/features/dashboard/components/subscription-recommendations.tsx'
import { SummaryCards } from '@/features/dashboard/components/summary-cards.tsx'
import { RecentReleaseSubscribes } from '@/features/dashboard/components/today-release-subscribes.tsx'
import {
  DASHBOARD_CONFIG_KEY,
  DASHBOARD_CONFIG_QUERY_KEY,
  isDashboardSectionVisible,
  resolveDashboardSections,
  type DashboardConfigPayload,
  type DashboardSectionKey,
} from '@/features/dashboard/dashboard-config.ts'

export function Dashboard() {
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'
  const { data: dashboardConfig } = useQuery({
    queryKey: DASHBOARD_CONFIG_QUERY_KEY,
    queryFn: async () => {
      const res = await getConfig<DashboardConfigPayload>(DASHBOARD_CONFIG_KEY)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const visibleSections = useMemo(
    () => resolveDashboardSections(dashboardConfig),
    [dashboardConfig]
  )

  const showDownloadDashboard = isDashboardSectionVisible(
    visibleSections,
    'download_dashboard'
  )
  const showSummaryCards = isDashboardSectionVisible(
    visibleSections,
    'summary_cards'
  )
  const showCategoryCards = isDashboardSectionVisible(
    visibleSections,
    'category_cards'
  )

  const { data: categoryTree } = useQuery({
    queryKey: ['category'],
    queryFn: async () => {
      const res = await getCategories()
      return res?.data
    },
    staleTime: 5 * 60 * 1000,
    enabled: showSummaryCards || showCategoryCards,
  })

  const data = useMemo(() => flattenSectionTotals(categoryTree ?? []), [categoryTree])

  const { data: state } = useQuery({
    queryKey: ['downloadState'],
    queryFn: async () => {
      const res = await getDownloadState()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
    enabled: showDownloadDashboard,
  })

  const sectionComponents: Partial<
    Record<DashboardSectionKey, React.ReactNode>
  > = {
    download_dashboard: (
      <DownloadDashboard
        data={state ?? { download_count: 0, section_count: [] }}
      />
    ),
    summary_cards: <SummaryCards data={data ?? []} />,
    recent_release_subscribes: <RecentReleaseSubscribes />,
    subscription_recommendations: <SubscriptionRecommendations />,
    movie_frequency_stats: <MovieFrequencyStatsPanel />,
    category_cards: <CategoryCards data={data ?? []} />,
  }

  return (
    <>
      <Header fixed>
        <Search />
        <div className='ms-auto flex items-center space-x-3'>
          <DashboardConfigSheet />
          <ServerLogDialog />
          <ImageModeSwitch />
          <ThemeSwitch />
          <ConfigDrawer />
        </div>
      </Header>

      <Main>
        <div>
          <ContentTitle
            title={isSimple ? '仪表盘' : '观星台'}
            description={
              isSimple
                ? '总览系统状态、近期更新和订阅推荐。'
                : '总览洞府灵机、近日新作与可纳之契。'
            }
            icon={<Mountain className='h-8 w-8 text-primary' />}
          />

          <div className='w-full space-y-4 md:space-y-6'>
            {visibleSections.map((sectionKey) => (
              <div key={sectionKey} className='w-full'>
                {sectionComponents[sectionKey]}
              </div>
            ))}

            {visibleSections.length === 0 && (
              <Card className='border-dashed'>
                <CardContent className='py-12 text-center text-sm text-muted-foreground'>
                  {isSimple
                    ? '当前没有显示任何组件，请通过右上角的配置面板添加。'
                    : '此刻观星台未陈列任何栏目，可通过右上角的面板重新布设。'}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </Main>
    </>
  )
}
