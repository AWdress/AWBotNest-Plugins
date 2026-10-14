import { useEffect, useRef } from 'react'
import { useRouterState } from '@tanstack/react-router'
import LoadingBar, { type LoadingBarRef } from 'react-top-loading-bar'
import { useIsMobile } from '@/hooks/use-mobile.tsx'

export function NavigationProgress() {
  const ref = useRef<LoadingBarRef>(null)
  const state = useRouterState()
  const isMobile = useIsMobile()
  useEffect(() => {
    if (state.status === 'pending') {
      ref.current?.continuousStart()
    } else {
      ref.current?.complete()
    }
  }, [state.status])

  if (isMobile) return null

  return (
    <LoadingBar
      color='var(--muted-foreground)'
      ref={ref}
      shadow={true}
      height={2}
      containerStyle={{
        position: 'fixed',
        top: 'env(safe-area-inset-top)', // 从安全区域下方开始
        left: 0,
        right: 0,
        zIndex: 9999,
      }}
    />
  )
}
