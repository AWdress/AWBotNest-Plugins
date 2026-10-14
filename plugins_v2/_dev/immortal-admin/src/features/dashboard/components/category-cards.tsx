import { Layers } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import type { Section } from '@/api/article.ts'

const COLOR_THEMES = [
  'from-blue-500/10 to-blue-500/30',
  'from-emerald-500/10 to-emerald-500/30',
  'from-violet-500/10 to-violet-500/30',
  'from-amber-500/10 to-amber-500/30',
  'from-rose-500/10 to-rose-500/30',
  'from-cyan-500/10 to-cyan-500/30',

  'from-indigo-500/10 to-indigo-500/30',
  'from-teal-500/10 to-teal-500/30',
  'from-fuchsia-500/10 to-fuchsia-500/30',
  'from-lime-500/10 to-lime-500/30',
  'from-orange-500/10 to-orange-500/30',
  'from-sky-500/10 to-sky-500/30',
]

export function CategoryCards({ data }: { data: Section[] }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 2xl:grid-cols-8">
      {data.map((cat, index) => {
        const color = COLOR_THEMES[index % COLOR_THEMES.length]

        return (
          <Card
            key={cat.name}
            className={`
              backdrop-blur-2xl
              bg-gradient-to-br ${color}
              transition hover:shadow-lg
            `}
          >
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-sm">{cat.name}</CardTitle>
              <Layers className="h-4 w-4 text-muted-foreground" />
            </CardHeader>

            <CardContent>
              <div className="text-2xl font-semibold tabular-nums">
                {cat.count.toLocaleString()}
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
