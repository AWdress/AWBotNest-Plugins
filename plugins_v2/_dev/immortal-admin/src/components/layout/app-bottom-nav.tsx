import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLocation, useNavigate } from '@tanstack/react-router'
import { MoreHorizontal, X } from 'lucide-react'
import { getVersion } from '@/api/user.ts'
import { useUIStore } from '@/stores/ui-store.ts'
import {
  useBottomNavData,
} from '@/components/layout/data/bottom-nav-data.ts'

export default function AppBottomNav() {
  const [showMore, setShowMore] = useState(false)
  const [isVisible, setIsVisible] = useState(true)
  const navigate = useNavigate()
  const location = useLocation()
  const lastScrollY = useRef(0)
  const hideBottomNav = useUIStore((s) => s.hideBottomNav)
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const { mainNavItems, moreMenuItems } = useBottomNavData()

  useEffect(() => {
    lastScrollY.current = 0
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsVisible(true)

    const timer = setTimeout(() => {
      const scrollContainer = document.querySelector(
        '[data-main-scroll-container]'
      ) as HTMLDivElement | null

      const handleScroll = () => {
        const currentScrollY = scrollContainer
          ? scrollContainer.scrollTop
          : window.scrollY

        if (currentScrollY > lastScrollY.current && currentScrollY > 10) {
          setIsVisible(false)
          setShowMore(false)
        } else if (currentScrollY < lastScrollY.current) {
          setIsVisible(true)
        }

        lastScrollY.current = currentScrollY
      }

      if (scrollContainer) {
        scrollContainer.addEventListener('scroll', handleScroll, {
          passive: true,
        })
        return () => {
          scrollContainer.removeEventListener('scroll', handleScroll)
        }
      }

      window.addEventListener('scroll', handleScroll, { passive: true })
      return () => {
        window.removeEventListener('scroll', handleScroll)
      }
    }, 100)

    return () => {
      clearTimeout(timer)
    }
  }, [location.pathname])

  const handleNavClick = (url: string) => {
    setShowMore(false)
    navigate({ to: url })
  }

  const handleMoreItemClick = (url: string) => {
    navigate({ to: url })
    setShowMore(false)
  }

  const isActive = (url: string) => location.pathname === url

  const { data } = useQuery({
    queryKey: ['version'],
    queryFn: async () => {
      const res = await getVersion()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const morePanelBottom = 'calc(env(safe-area-inset-bottom, 0px) + 6rem)'

  return (
    <>
      {showMore && (
        <div
          className='fixed inset-0 z-40 animate-in bg-background/25 backdrop-blur-xl duration-200 fade-in'
          onClick={() => setShowMore(false)}
        >
          <div
            className='absolute right-4 left-4 mx-auto max-w-md animate-in overflow-hidden rounded-3xl border border-amber-500/15 bg-background/55 shadow-[0_24px_80px_rgba(12,18,16,0.28)] backdrop-blur-2xl duration-300 slide-in-from-bottom-4'
            style={{ bottom: morePanelBottom }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className='flex items-center justify-between border-b border-amber-500/10 px-6 py-3'>
              <h3 className='text-lg font-semibold text-foreground'>
                {routeNamingMode === 'simple' ? '更多选项' : '天机阁'}
              </h3>
              <button
                onClick={() => setShowMore(false)}
                className='rounded-xl border border-border/60 bg-background/50 p-1.5 text-muted-foreground transition-colors hover:border-amber-500/30 hover:text-foreground'
              >
                <X className='h-4 w-4' />
              </button>
            </div>

            <div className='max-h-128 overflow-y-auto px-4 py-3'>
              {moreMenuItems.map((group, groupIndex) => (
                <div key={groupIndex} className='mb-4 last:mb-0'>
                  <div className='mb-2 px-3 text-xs font-medium tracking-[0.18em] text-muted-foreground/90'>
                    {group.title}
                  </div>
                  <div className='space-y-1'>
                    {group.items.map((item) => {
                      const Icon = item.icon
                      const active = isActive(item.url)

                      return (
                        <button
                          key={item.id}
                          onClick={() => handleMoreItemClick(item.url)}
                          className={`flex w-full items-center gap-3 rounded-2xl border px-4 py-3 transition-all ${
                            active
                              ? 'border-amber-500/20 bg-amber-500/10 text-amber-700 shadow-[0_8px_28px_rgba(217,119,6,0.12)] dark:text-amber-300'
                              : 'border-border/50 bg-background/40 text-foreground/85 hover:border-emerald-500/15 hover:bg-emerald-500/6'
                          }`}
                        >
                          <span
                            className={`flex size-9 items-center justify-center rounded-xl border ${
                              active
                                ? 'border-amber-500/25 bg-amber-500/12 text-amber-700 dark:text-amber-300'
                                : 'border-emerald-500/12 bg-emerald-500/7 text-emerald-700 dark:text-emerald-300'
                            }`}
                          >
                            <Icon className='h-4.5 w-4.5' />
                          </span>
                          <span className='font-medium'>{item.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
              <div className='flex justify-end px-4 pt-2 text-xs text-muted-foreground'>
                当前版本: {data}
              </div>
            </div>
          </div>
        </div>
      )}
      <nav
        className={`pointer-events-none fixed right-0 bottom-0 left-0 z-50 transition-all duration-300 ease-in-out ${
          isVisible && !hideBottomNav
            ? 'translate-y-0 opacity-100'
            : 'translate-y-[120%] opacity-0'
        }`}
      >
        <div
          className='pointer-events-none flex items-end justify-center px-4 pt-2'
          style={{
            paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 0.5rem)',
          }}
        >
          <div className='pointer-events-auto relative w-full max-w-md overflow-hidden rounded-4xl border border-amber-500/15 bg-background/45 shadow-[0_20px_60px_rgba(10,20,18,0.22)] backdrop-blur-2xl'>
            <div className='flex items-center justify-around px-2 py-1'>
              {mainNavItems.map((item) => {
                const Icon = item.icon
                const active = isActive(item.url)

                return (
                  <button
                    key={item.id}
                    onClick={() => handleNavClick(item.url)}
                    className={`relative flex min-w-16.25 flex-col items-center justify-center rounded-[1.4rem] px-3 py-1.5 transition-all duration-200 ease-out active:scale-95 ${
                      active && !showMore
                        ? 'bg-amber-500/10 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.18)]'
                        : 'hover:bg-emerald-500/6'
                    }`}
                  >
                    <span
                      className={`mb-1 flex size-9 items-center justify-center rounded-2xl border transition-all ${
                        active && !showMore
                          ? 'border-amber-500/28 bg-amber-500/14 text-amber-700 shadow-[0_0_22px_rgba(245,158,11,0.14)] dark:text-amber-300'
                          : 'border-emerald-500/12 bg-emerald-500/7 text-emerald-700 dark:text-emerald-300'
                      }`}
                    >
                      <Icon
                        className='h-4.5 w-4.5'
                        strokeWidth={active ? 2.35 : 2}
                      />
                    </span>

                    <span
                      className={`text-[11px] font-medium transition-colors ${
                        active && !showMore
                          ? 'text-amber-700 dark:text-amber-300'
                          : 'text-foreground/78'
                      }`}
                    >
                      {item.label}
                    </span>
                  </button>
                )
              })}

              <button
                onClick={() => setShowMore(!showMore)}
                className={`relative flex min-w-16.25 flex-col items-center justify-center rounded-[1.4rem] px-3 py-1.5 transition-all duration-200 ease-out active:scale-95 ${
                  showMore
                    ? 'bg-amber-500/10 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.18)]'
                    : 'hover:bg-emerald-500/6'
                }`}
              >
                <span
                  className={`mb-1 flex size-9 items-center justify-center rounded-2xl border transition-all ${
                    showMore
                      ? 'border-amber-500/28 bg-amber-500/14 text-amber-700 shadow-[0_0_22px_rgba(245,158,11,0.14)] dark:text-amber-300'
                      : 'border-emerald-500/12 bg-emerald-500/7 text-emerald-700 dark:text-emerald-300'
                  }`}
                >
                  <MoreHorizontal
                    className='h-4.5 w-4.5'
                    strokeWidth={showMore ? 2.35 : 2}
                  />
                </span>

                <span
                  className={`text-[11px] font-medium transition-colors ${
                    showMore
                      ? 'text-amber-700 dark:text-amber-300'
                      : 'text-foreground/78'
                  }`}
                >
                  更多
                </span>
              </button>
            </div>
          </div>
        </div>
      </nav>
    </>
  )
}
