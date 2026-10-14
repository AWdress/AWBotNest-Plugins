import { useUIStore } from '@/stores/ui-store'
import { Sparkles, Type } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'

export function RouteNamingForm() {
  const { routeNamingMode, setRouteNamingMode } = useUIStore()
  const isSimple = routeNamingMode === 'simple'

  return (
    <Card>
      <CardHeader>
        <CardTitle className='flex items-center gap-2'>
          <Type className='h-5 w-5' />
          界面命名风格
        </CardTitle>
        <CardDescription>
          选择使用通俗易懂或仙侠风格的界面命名
        </CardDescription>
      </CardHeader>
      <CardContent className='flex flex-col gap-4'>
        <div className='flex gap-4'>
          <Button
            variant={isSimple ? 'default' : 'outline'}
            onClick={() => setRouteNamingMode('simple')}
            className='flex-1'
          >
            <Type className='mr-2 h-4 w-4' />
            通俗版
          </Button>
          <Button
            variant={!isSimple ? 'default' : 'outline'}
            onClick={() => setRouteNamingMode('fantasy')}
            className='flex-1'
          >
            <Sparkles className='mr-2 h-4 w-4' />
            仙侠版
          </Button>
        </div>
        <p className='text-sm text-muted-foreground'>
          {isSimple
            ? '当前使用通俗易懂的命名，如"仪表盘"、"任务管理"、"系统设置"等'
            : '当前使用仙侠风格命名，如"观星台"、"时轮殿"、"道枢"等'}
        </p>
      </CardContent>
    </Card>
  )
}
