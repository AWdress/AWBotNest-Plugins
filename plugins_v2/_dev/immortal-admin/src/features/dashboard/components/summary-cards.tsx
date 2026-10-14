import { Database, Layers, Sparkles } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card.tsx'
import type { Section } from '@/api/article.ts'

/** 修炼等级阈值定义（累计资源） */
const REALM_LEVELS = [
  { name: '灵气枯竭', threshold: 0 },
  { name: '灵气稀薄', threshold: 5_000 },
  { name: '灵气平稳', threshold: 20_000 },
  { name: '灵气充沛', threshold: 200_000 },
  { name: '灵气鼎盛', threshold: 300_000 },
]

function getRealm(total: number) {
  for (let i = REALM_LEVELS.length - 1; i >= 0; i--) {
    if (total >= REALM_LEVELS[i].threshold) {
      const current = REALM_LEVELS[i]
      const next = REALM_LEVELS[i + 1]
      return {
        current,
        next,
      }
    }
  }
  return {
    current: REALM_LEVELS[0],
    next: REALM_LEVELS[1],
  }
}

export function SummaryCards({ data }: { data: Section[] }) {
  const total = data.reduce((sum, c) => sum + c.count, 0)
  const realm = getRealm(total)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* 分类数 */}
      <Card className="relative overflow-hidden bg-gradient-to-br from-primary/10 via-background to-background border-primary/20">
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-primary/10 blur-2xl" />
        <CardContent className="flex items-center gap-4 p-6">
          <div className="rounded-xl bg-primary/15 p-3">
            <Layers className="h-6 w-6 text-primary" />
          </div>
          <div>
            <div className="text-sm text-muted-foreground">天地属性</div>
            <div className="text-3xl font-bold tracking-tight">
              {data.length}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 总资源数 */}
      <Card className="relative overflow-hidden bg-gradient-to-br from-emerald-500/10 via-background to-background border-emerald-500/20">
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-emerald-500/10 blur-2xl" />
        <CardContent className="flex items-center gap-4 p-6">
          <div className="rounded-xl bg-emerald-500/15 p-3">
            <Database className="h-6 w-6 text-emerald-500" />
          </div>
          <div>
            <div className="text-sm text-muted-foreground">灵力总数</div>
            <div className="text-3xl font-bold tracking-tight tabular-nums">
              {total.toLocaleString()}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 当前修炼等级 */}
      <Card className="relative overflow-hidden bg-gradient-to-br from-purple-500/10 via-background to-background border-purple-500/20">
        <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-purple-500/10 blur-2xl" />
        <CardContent className="flex items-center gap-4 p-6">
          <div className="rounded-xl bg-purple-500/15 p-3">
            <Sparkles className="h-6 w-6 text-purple-500" />
          </div>
          <div>
            <div className="text-sm text-muted-foreground">
              此方天地
            </div>
            <div className="text-2xl font-bold tracking-tight">
              {realm.current.name}
            </div>

            {realm.next && (
              <div className="mt-1 text-xs text-muted-foreground">
                距离 {realm.next.name} 还需{' '}
                <span className="tabular-nums">
                  {(realm.next.threshold - total).toLocaleString()}
                </span> 灵力
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
