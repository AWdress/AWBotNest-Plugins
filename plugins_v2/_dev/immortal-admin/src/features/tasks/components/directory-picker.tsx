import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, ChevronUp, FolderTree, LoaderCircle, RotateCcw } from 'lucide-react'
import { browseTaskDirectories } from '@/api/task.ts'
import { Button } from '@/components/ui/button.tsx'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
} from '@/components/ui/dialog.tsx'
import { Input } from '@/components/ui/input.tsx'

export function DirectoryPicker({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}) {
  const [open, setOpen] = useState(false)
  const [browsePath, setBrowsePath] = useState('')
  const [draftPath, setDraftPath] = useState('')

  useEffect(() => {
    if (!open) return
    const initialPath = value.trim()
    setBrowsePath(initialPath)
    setDraftPath(initialPath)
  }, [open, value])

  const { data, isFetching } = useQuery({
    queryKey: ['task-directory-browse', browsePath],
    queryFn: async () => {
      const res = await browseTaskDirectories(browsePath || undefined)
      return res.data
    },
    enabled: open,
    staleTime: 30 * 1000,
  })

  const currentPath = data?.current_path ?? ''
  const canSelectCurrent = Boolean(currentPath)

  return (
    <>
      <div className='flex gap-2'>
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder ?? '请输入目录路径'}
        />
        <Button type='button' variant='outline' onClick={() => setOpen(true)}>
          <FolderTree className='h-4 w-4' />
          选择目录
        </Button>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
        <DialogContent className='max-w-2xl bg-background/80 backdrop-blur-lg'>
          <DialogHeader>
            <DialogTitle>选择目录</DialogTitle>
          </DialogHeader>

          <div className='space-y-4'>
            <div className='flex flex-col gap-2 md:flex-row'>
              <Input
                value={draftPath}
                onChange={(event) => setDraftPath(event.target.value)}
                placeholder='输入目录后点击跳转'
                className='font-mono text-xs'
              />
              <Button type='button' variant='outline' onClick={() => setBrowsePath(draftPath.trim())}>
                跳转
              </Button>
              <Button
                type='button'
                variant='outline'
                disabled={!data?.parent_path}
                onClick={() => {
                  const nextPath = data?.parent_path ?? ''
                  setBrowsePath(nextPath)
                  setDraftPath(nextPath)
                }}
              >
                <ChevronUp className='h-4 w-4' />
                上级
              </Button>
              <Button
                type='button'
                variant='outline'
                onClick={() => {
                  setBrowsePath('')
                  setDraftPath('')
                }}
              >
                <RotateCcw className='h-4 w-4' />
                根目录
              </Button>
            </div>

            <div className='rounded-md border bg-muted/20 p-3'>
              <p className='text-xs text-muted-foreground'>当前目录</p>
              <p className='break-all font-mono text-xs'>
                {currentPath || '请选择磁盘或输入目录路径'}
              </p>
            </div>

            <div className='max-h-80 space-y-2 overflow-y-auto rounded-md border p-2'>
              {isFetching && (
                <div className='flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground'>
                  <LoaderCircle className='h-4 w-4 animate-spin' />
                  加载目录中...
                </div>
              )}

              {!isFetching && data?.items.length === 0 && (
                <div className='py-6 text-center text-sm text-muted-foreground'>当前目录下没有可进入的子目录</div>
              )}

              {!isFetching && data?.items.map((item) => (
                <button
                  key={item.path}
                  type='button'
                  className='flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors hover:bg-muted/40'
                  onClick={() => {
                    setBrowsePath(item.path)
                    setDraftPath(item.path)
                  }}
                >
                  <span className='truncate'>{item.name}</span>
                  <span className='text-xs text-muted-foreground'>进入</span>
                </button>
              ))}
            </div>

            <div className='flex justify-end gap-2'>
              <Button type='button' variant='ghost' onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button
                type='button'
                disabled={!canSelectCurrent}
                onClick={() => {
                  onChange(currentPath)
                  setOpen(false)
                }}
              >
                <Check className='h-4 w-4' />
                使用当前目录
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
