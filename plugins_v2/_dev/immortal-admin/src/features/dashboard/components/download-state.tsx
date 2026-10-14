import ReactECharts from 'echarts-for-react';
import type { DownloadState, SectionCount } from '@/api/download-log.ts';
import { useTheme } from '@/context/theme-provider.tsx';
import { Card, CardContent, CardFooter } from '@/components/ui/card';



































































const COLORS_LIGHT = [
  '#FF6B9D',
  '#C44569',
  '#FFA07A',
  '#FFD93D',
  '#6BCB77',
  '#4D96FF',
  '#9D84B7',
  '#FF8C42',
  '#38E4AE',
  '#FF6B9D',
]

const COLORS_DARK = [
  '#FF7EB3',
  '#FF6B9D',
  '#FFB347',
  '#FFE66D',
  '#7FE5A8',
  '#5DADE2',
  '#BB8FCE',
  '#FFAB73',
  '#4ECDC4',
  '#F39C12',
]

const LEVELS = [
  // 练气
  {
    threshold: 0,
    label: '练气初期',
    color: 'text-slate-500',
    bgColor: 'bg-slate-100 dark:bg-slate-800',
    progressColor: 'bg-slate-500',
    icon: '🌱',
  },
  {
    threshold: 10,
    label: '练气中期',
    color: 'text-slate-500',
    bgColor: 'bg-slate-100 dark:bg-slate-800',
    progressColor: 'bg-slate-500',
    icon: '🌱',
  },
  {
    threshold: 25,
    label: '练气后期',
    color: 'text-slate-600',
    bgColor: 'bg-slate-100 dark:bg-slate-800',
    progressColor: 'bg-slate-600',
    icon: '🌱',
  },
  {
    threshold: 50,
    label: '练气巅峰',
    color: 'text-slate-700 dark:text-slate-300',
    bgColor: 'bg-slate-200 dark:bg-slate-700',
    progressColor: 'bg-slate-700 dark:bg-slate-300',
    icon: '🌱',
  },

  // 筑基
  {
    threshold: 100,
    label: '筑基初期',
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-950',
    progressColor: 'bg-blue-500',
    icon: '🌿',
  },
  {
    threshold: 180,
    label: '筑基中期',
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-950',
    progressColor: 'bg-blue-500',
    icon: '🌿',
  },
  {
    threshold: 300,
    label: '筑基后期',
    color: 'text-blue-700 dark:text-blue-300',
    bgColor: 'bg-blue-100 dark:bg-blue-900',
    progressColor: 'bg-blue-600',
    icon: '🌿',
  },
  {
    threshold: 500,
    label: '筑基巅峰',
    color: 'text-blue-800 dark:text-blue-200',
    bgColor: 'bg-blue-100 dark:bg-blue-900',
    progressColor: 'bg-blue-700',
    icon: '🌿',
  },

  // 结丹
  {
    threshold: 800,
    label: '结丹初期',
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-950',
    progressColor: 'bg-green-500',
    icon: '🟡',
  },
  {
    threshold: 1200,
    label: '结丹中期',
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-950',
    progressColor: 'bg-green-500',
    icon: '🟡',
  },
  {
    threshold: 1800,
    label: '结丹后期',
    color: 'text-green-700 dark:text-green-300',
    bgColor: 'bg-green-100 dark:bg-green-900',
    progressColor: 'bg-green-600',
    icon: '🟡',
  },
  {
    threshold: 3000,
    label: '结丹巅峰',
    color: 'text-green-800 dark:text-green-200',
    bgColor: 'bg-green-100 dark:bg-green-900',
    progressColor: 'bg-green-700',
    icon: '🟡',
  },

  // 元婴
  {
    threshold: 5000,
    label: '元婴初期',
    color: 'text-orange-600 dark:text-orange-400',
    bgColor: 'bg-orange-50 dark:bg-orange-950',
    progressColor: 'bg-orange-500',
    icon: '👶',
  },
  {
    threshold: 8000,
    label: '元婴中期',
    color: 'text-orange-600 dark:text-orange-400',
    bgColor: 'bg-orange-50 dark:bg-orange-950',
    progressColor: 'bg-orange-500',
    icon: '👶',
  },
  {
    threshold: 12000,
    label: '元婴后期',
    color: 'text-orange-700 dark:text-orange-300',
    bgColor: 'bg-orange-100 dark:bg-orange-900',
    progressColor: 'bg-orange-600',
    icon: '👶',
  },
  {
    threshold: 18000,
    label: '元婴巅峰',
    color: 'text-orange-800 dark:text-orange-200',
    bgColor: 'bg-orange-100 dark:bg-orange-900',
    progressColor: 'bg-orange-700',
    icon: '👶',
  },

  // 化神
  {
    threshold: 25000,
    label: '化神初期',
    color: 'text-purple-600 dark:text-purple-400',
    bgColor: 'bg-purple-50 dark:bg-purple-950',
    progressColor: 'bg-purple-500',
    icon: '🧒',
  },
  {
    threshold: 32000,
    label: '化神中期',
    color: 'text-purple-600 dark:text-purple-400',
    bgColor: 'bg-purple-50 dark:bg-purple-950',
    progressColor: 'bg-purple-500',
    icon: '🧒',
  },
  {
    threshold: 40000,
    label: '化神后期',
    color: 'text-purple-700 dark:text-purple-300',
    bgColor: 'bg-purple-100 dark:bg-purple-900',
    progressColor: 'bg-purple-600',
    icon: '🧒',
  },
  {
    threshold: 50000,
    label: '化神巅峰',
    color: 'text-purple-800 dark:text-purple-200',
    bgColor: 'bg-purple-100 dark:bg-purple-900',
    progressColor: 'bg-purple-700',
    icon: '🧒',
  },
]

const getLevel = (count: number) => {
  for (let i = LEVELS.length - 1; i >= 0; i--) {
    if (count >= LEVELS[i].threshold) {
      return LEVELS[i]
    }
  }
  return LEVELS[0]
}

function NightingaleChart({
                            data,
                            title,
                          }: {
  data: SectionCount[]
  title?: string
}) {
  const { theme } = useTheme()
  const option = {
    tooltip: {
      trigger: 'item',
    },
    series: [
      {
        name: title,
        type: 'pie',
        roseType: 'area',
        radius: ['10%', '85%'],
        data: data.map((d) => ({
          name: d.section,
          value: d.count,
        })),
        label: {
          color: theme === 'dark' ? '#fff' : '#333',
          textBorderWidth: 2,
          fontSize: 14,
          fontWeight: 'bold',
        },
      },
    ],
  }

  return (
    <div className='h-[380px]'>
      <ReactECharts style={{ height: '100%' }} option={option} />
    </div>
  )
}

export function DownloadDashboard({ data }: { data: DownloadState }) {
  const isDark = useTheme().theme === 'dark'
  const COLORS = isDark ? COLORS_DARK : COLORS_LIGHT

  const currentLevel = getLevel(data.download_count)
  const currentLevelIndex = LEVELS.findIndex(
    (l) => l.label === currentLevel.label
  )
  const nextLevel = LEVELS[currentLevelIndex + 1]
  const progress = nextLevel
    ? Math.min(
      ((data.download_count - currentLevel.threshold) /
        (nextLevel.threshold - currentLevel.threshold)) *
      100,
      100
    )
    : 100

  const total = data.section_count.reduce((sum, item) => sum + item.count, 0)

  return (
    <div className='grid gap-6 lg:grid-cols-2'>
      <Card className='flex flex-col justify-center border-none shadow-none'>
        <CardContent>
          <div className='flex items-baseline gap-2'>
            <span className='text-5xl font-extrabold tracking-tight'>
              {data.download_count.toLocaleString()}
            </span>
            <span className='text-sm text-muted-foreground'>灵力</span>
          </div>
          <div className='mt-4 space-y-2'>
            <div
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold ${currentLevel.bgColor} ${currentLevel.color}`}
            >
              <span className='text-base'>{currentLevel.icon}</span>
              <span>{currentLevel.label}</span>
            </div>

            {nextLevel && (
              <div className='space-y-1.5'>
                <div className='flex items-center justify-between text-xs text-muted-foreground'>
                  <span>距离 {nextLevel.label}</span>
                  <span className='font-medium'>{Math.round(progress)}%</span>
                </div>
                <div className='h-2 w-full overflow-hidden rounded-full bg-muted'>
                  <div
                    className={`h-full transition-all duration-500 ease-out ${currentLevel.progressColor}`}
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className='text-xs text-muted-foreground'>
                  还需{' '}
                  <span className='font-semibold text-foreground'>
                    {(
                      nextLevel.threshold - data.download_count
                    ).toLocaleString()}
                  </span>{' '}
                  次下载
                </p>
              </div>
            )}

            {!nextLevel && (
              <p className='text-xs font-medium text-amber-600 dark:text-amber-400'>
                ✨ 已达到最高等级！
              </p>
            )}
          </div>

          <div className='mt-6 space-y-3'>
            <p className='text-sm font-medium text-muted-foreground'>
              各灵根吸取状态
            </p>
            {data.section_count
              .sort((a, b) => b.count - a.count)
              .map((item, index) => {
                const percentage =
                  total > 0 ? ((item.count / total) * 100).toFixed(1) : '0.0'
                return (
                  <div key={item.section} className='flex items-center gap-3'>
                    <div
                      className='h-3 w-3 flex-shrink-0 rounded-sm'
                      style={{ backgroundColor: COLORS[index % COLORS.length] }}
                    />
                    <div className='flex flex-1 items-center justify-between text-sm'>
                      <span className='font-medium'>{item.section}</span>
                      <div className='flex items-baseline gap-2'>
                        <span className='font-semibold'>
                          {item.count.toLocaleString()}
                        </span>
                        <span className='text-xs text-muted-foreground'>
                          {percentage}%
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
          </div>
        </CardContent>
      </Card>

      <Card className='flex flex-col border-none shadow-none'>
        <CardContent>
          <NightingaleChart data={data.section_count} title={'灵根分布'} />
        </CardContent>
        <CardFooter className='flex-col gap-2 text-center text-xs text-muted-foreground italic'></CardFooter>
      </Card>
    </div>
  )
}