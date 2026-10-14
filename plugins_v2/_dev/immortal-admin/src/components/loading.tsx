import { Loader2 } from "lucide-react"

export function Loading() {
  return (
    <div className="flex h-40 items-center justify-center text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin mr-2" />
      加载中...
    </div>
  )
}
