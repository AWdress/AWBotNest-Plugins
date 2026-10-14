import { useNavigate, useRouter } from '@tanstack/react-router'
import { Button } from '@/components/ui/button'
import { useUIStore } from '@/stores/ui-store'

export function NotFoundError() {
  const navigate = useNavigate()
  const { history } = useRouter()
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  return (
    <div className='h-svh'>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
        <h1 className='text-[7rem] leading-tight font-bold'>404</h1>
        <span className='font-medium'>
          {isSimple ? '页面不存在' : '此页遁入虚空，机缘难觅'}
        </span>
        <p className='text-center text-muted-foreground'>
          {isSimple ? (
            <>
              您访问的页面不存在或已被移除。
            </>
          ) : (
            <>
              你所寻之处，或已湮灭于时空裂隙。
              <br />
              也可能被大能挥袖抹去，不留踪迹。
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
