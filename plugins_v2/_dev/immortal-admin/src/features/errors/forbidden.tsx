import { useNavigate, useRouter } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { useUIStore } from '@/stores/ui-store'

export function ForbiddenError() {
  const navigate = useNavigate()
  const { history } = useRouter()
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <div className='h-svh'>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
        <h1 className='text-[7rem] leading-tight font-bold'>403</h1>
        <span className='font-medium'>
          {isSimple ? '无访问权限' : '仙门禁制，未得通行法旨'}
        </span>
        <p className='text-center text-muted-foreground'>
          {isSimple ? (
            <>您没有权限访问该页面。</>
          ) : (
            <>
              此处设有护山禁制，道友当前修为与令牌 <br />
              尚不足以观阅此间机缘。
            </>
          )}
        </p>
        <div className='mt-6 flex gap-4'>
          <Button variant='outline' onClick={() => history.go(-1)}>
            {isSimple ? '返回' : '返回来路'}
          </Button>
          <Button onClick={() => navigate({ to: '/' })}>
            {isSimple ? '返回首页' : '回洞府'}
          </Button>
        </div>
      </div>
    </div>
  )
}
