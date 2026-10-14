import { useState } from 'react'
import { Award, Crown, Film } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ConfigDrawer } from '@/components/config-drawer'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch'
import { useUIStore } from '@/stores/ui-store'
import { RankList as CastRankList } from '@/features/rank/cast/rank-list.tsx'
import { RANK_MOVIE_SITES } from '@/features/rank/movie/rank-filter.tsx'
import { RankList as MovieRankList } from '@/features/rank/movie/rank-list.tsx'

export type RankTab = 'movie' | 'cast'

export function RankPage({ defaultTab = 'movie' }: { defaultTab?: RankTab }) {
  const [tabValue, setTabValue] = useState(defaultTab)
  const [movieSiteId, setMovieSiteId] = useState(
    RANK_MOVIE_SITES[0]?.id ?? 'library'
  )
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <>
      <Header fixed>
        <Search />
        <div className='ms-auto flex items-center space-x-4'>
          <ServerLogDialog />
          <ImageModeSwitch />
          <ThemeSwitch />
          <ConfigDrawer />
        </div>
      </Header>

      <Main fixed>
        <ContentTitle
          title={isSimple ? '排行榜' : '天榜'}
          description={
            isSimple
              ? '查看各平台的影片和演员排行榜。'
              : '观诸榜起落，择可纳入灵契之作与人。'
          }
          icon={<Award className='h-8 w-8 text-primary' />}
        />
        <div className='-mx-4 flex flex-col space-y-3 overflow-hidden md:mx-0 md:w-full'>
          <div className='mx-4 shrink-0 space-y-3'>
            <Tabs
              defaultValue={defaultTab}
              onValueChange={(value) => setTabValue(value as RankTab)}
            >
              <TabsList
                className='w-full gap-2 bg-transparent p-0'
              >
                <TabsTrigger
                  value='movie'
                  className='group gap-2 rounded-2xl border border-border/60 bg-background/45 px-3 py-2 text-foreground/78 transition-all data-[state=active]:border-amber-500/20 data-[state=active]:bg-amber-500/10 data-[state=active]:text-amber-700 data-[state=active]:shadow-[0_10px_30px_rgba(245,158,11,0.08)] dark:data-[state=active]:text-amber-300'
                >
                  <span className='me-1 flex size-8 items-center justify-center rounded-xl border border-emerald-500/12 bg-emerald-500/7 text-emerald-700 transition-all group-data-[state=active]:border-amber-500/25 group-data-[state=active]:bg-amber-500/12 group-data-[state=active]:text-amber-700 dark:text-emerald-300 dark:group-data-[state=active]:text-amber-300'>
                    <Film className='h-4 w-4' />
                  </span>
                  影片榜单
                </TabsTrigger>
                <TabsTrigger
                  value='cast'
                  className='group gap-2 rounded-2xl border border-border/60 bg-background/45 px-3 py-2 text-foreground/78 transition-all data-[state=active]:border-amber-500/20 data-[state=active]:bg-amber-500/10 data-[state=active]:text-amber-700 data-[state=active]:shadow-[0_10px_30px_rgba(245,158,11,0.08)] dark:data-[state=active]:text-amber-300'
                >
                  <span className='me-1 flex size-8 items-center justify-center rounded-xl border border-emerald-500/12 bg-emerald-500/7 text-emerald-700 transition-all group-data-[state=active]:border-amber-500/25 group-data-[state=active]:bg-amber-500/12 group-data-[state=active]:text-amber-700 dark:text-emerald-300 dark:group-data-[state=active]:text-amber-300'>
                    <Crown className='h-4 w-4' />
                  </span>
                  演员榜单
                </TabsTrigger>
              </TabsList>
            </Tabs>
            {tabValue === 'movie' && (
              <Tabs value={movieSiteId} onValueChange={setMovieSiteId}>
                <TabsList className='w-full gap-2 bg-transparent p-0'>
                  {RANK_MOVIE_SITES.map((site) => (
                    <TabsTrigger
                      key={site.id}
                      value={site.id}
                      className='rounded-xl border border-border/50 bg-background/35 px-3 py-1.5 text-foreground/72 transition-all data-[state=active]:border-amber-500/15 data-[state=active]:bg-amber-500/8 data-[state=active]:text-amber-700 dark:data-[state=active]:text-amber-300'
                    >
                      {site.name}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            )}
          </div>
          <div
            className='scrollbar-hide flex-1 overflow-auto'
            data-main-scroll-container
          >
            {tabValue === 'movie' && (
              <MovieRankList key={movieSiteId} defaultSiteId={movieSiteId} />
            )}
            {tabValue === 'cast' && <CastRankList />}
          </div>
        </div>
      </Main>
    </>
  )
}
