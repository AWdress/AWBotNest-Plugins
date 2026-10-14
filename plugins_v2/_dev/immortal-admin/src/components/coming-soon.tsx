import { Telescope } from 'lucide-react'
import { useUIStore } from '@/stores/ui-store'

export function ComingSoon() {
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <div className='h-svh'>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-3 text-center'>
        <Telescope size={72} />
        <h1 className='text-4xl leading-tight font-bold'>
          {isSimple ? '即将上线' : '问道台'}
        </h1>
        <p className='max-w-md text-muted-foreground'>
          {isSimple
            ? '该功能正在开发中，请耐心等待。'
            : '此处道卷尚在编纂，灵机未满之前，暂且静候片刻。'}
        </p>
      </div>
    </div>
  )
}
