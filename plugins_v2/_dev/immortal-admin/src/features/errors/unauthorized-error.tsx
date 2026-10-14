import { useNavigate, useRouter } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { useUIStore } from '@/stores/ui-store'

export function UnauthorisedError() {
  const navigate = useNavigate()
  const { history } = useRouter()
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <div className='h-svh'>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
        <h1 className='text-[7rem] leading-tight font-bold'>401</h1>
        <span className='font-medium'>
          {isSimple ? '未授权访问' : '道友尚未验明正身'}
        </span>
        <p className='text-center text-muted-foreground'>
          {isSimple ? (
            <>请先登录后再访问该页面。</>
          ) : (
            <>
              请先持正统令牌入阵验身，
              <br />
              再来叩问此处机缘。
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
