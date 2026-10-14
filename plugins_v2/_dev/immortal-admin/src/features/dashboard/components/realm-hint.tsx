import { Info } from 'lucide-react'

interface RealmHintProps {
  total?: number
}

export function RealmHint({ total }: RealmHintProps) {
  return (
    <div
      className="
        mt-6 flex gap-3 rounded-xl border
        bg-muted/40 px-5 py-4
        text-sm text-muted-foreground
      "
    >
      <Info className="mt-0.5 h-4 w-4 shrink-0" />

      <div className="space-y-1 leading-relaxed">
        <div>
          修炼等级依据 <span className="font-medium text-foreground">累计资源</span> 判定：
        </div>

        <div className="tabular-nums">
          炼气（0） → 筑基（5,000） → 结丹（20,000） → 元婴（200,000） → 化神（300,000）
        </div>

        <div>
          当前资源为{' '}
          <span className="font-medium text-foreground tabular-nums">
            {total?.toLocaleString()}
          </span>
          ，境界仅供展示，不代表必然突破。
        </div>
      </div>
    </div>
  )
}
