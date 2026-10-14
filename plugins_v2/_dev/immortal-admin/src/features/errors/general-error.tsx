import { useNavigate, useRouter } from '@tanstack/react-router'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { useUIStore } from '@/stores/ui-store'

type GeneralErrorProps = React.HTMLAttributes<HTMLDivElement> & {
  minimal?: boolean
}

export function GeneralError({
  className,
  minimal = false,
}: GeneralErrorProps) {
  const navigate = useNavigate()
  const { history } = useRouter()
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <div className={cn('h-svh w-full', className)}>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
        {!minimal && (
          <h1 className='text-[7rem] leading-tight font-bold'>500</h1>
        )}
        <span className='font-medium'>
          {isSimple ? '服务器错误' : '天机紊乱，灵阵失衡'}
        </span>
        <p className='text-center text-muted-foreground'>
          {isSimple ? (
            <>服务器发生错误，请稍后重试。</>
          ) : (
            <>
              方才推演时出了岔子。
              <br /> 请道友稍候片刻，再行运转。
            </>
          )}
        </p>
        {!minimal && (
          <div className='mt-6 flex gap-4'>
            <Button variant='outline' onClick={() => history.go(-1)}>
              {isSimple ? '返回' : '返回来路'}
            </Button>
            <Button onClick={() => navigate({ to: '/' })}>
              {isSimple ? '返回首页' : '回洞府'}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
