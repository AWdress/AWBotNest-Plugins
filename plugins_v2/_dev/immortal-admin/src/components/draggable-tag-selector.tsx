import { useRef, useState, type TouchEvent } from 'react'
import { GripVertical, Plus, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu.tsx'

export function DraggableTagSelector({
  options,
  value,
  onChange,
  placeholder = '暂未选择',
  addLabel = '添加',
}: {
  options: string[]
  value: string[]
  onChange: (v: string[]) => void
  placeholder?: string
  addLabel?: string
}) {
  const available = options.filter((o) => !value.includes(o))
  const dragIndex = useRef<number | null>(null)
  const [dragOver, setDragOver] = useState<number | null>(null)

  const add = (item: string) => onChange([...value, item])
  const remove = (item: string) => onChange(value.filter((v) => v !== item))

  const moveItem = (fromIndex: number, toIndex: number) => {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) {
      return
    }
    const next = [...value]
    const [moved] = next.splice(fromIndex, 1)
    next.splice(toIndex, 0, moved)
    onChange(next)
    dragIndex.current = toIndex
    setDragOver(toIndex)
  }

  const onDragStart = (i: number) => {
    dragIndex.current = i
    setDragOver(i)
  }

  const onDragEnter = (i: number) => {
    if (dragIndex.current === null || dragIndex.current === i) {
      return
    }
    moveItem(dragIndex.current, i)
  }

  const onDrop = () => {
    dragIndex.current = null
    setDragOver(null)
  }

  const onDragEnd = () => {
    dragIndex.current = null
    setDragOver(null)
  }

  const onTouchStart = (index: number) => (event: TouchEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    dragIndex.current = index
    setDragOver(index)
  }

  const onTouchMove = (event: TouchEvent<HTMLButtonElement>) => {
    if (dragIndex.current === null) {
      return
    }
    event.preventDefault()
    event.stopPropagation()
    const touch = event.touches[0]
    if (!touch) {
      return
    }
    const target = document
      .elementFromPoint(touch.clientX, touch.clientY)
      ?.closest<HTMLElement>('[data-draggable-tag-index]')
    const nextIndex = target?.dataset.draggableTagIndex
    if (nextIndex == null) {
      return
    }
    const index = Number(nextIndex)
    if (Number.isNaN(index) || index === dragIndex.current) {
      return
    }
    moveItem(dragIndex.current, index)
  }

  const onTouchEnd = (event: TouchEvent<HTMLButtonElement>) => {
    event.stopPropagation()
    onDragEnd()
  }

  return (
    <div className='flex min-h-9 flex-wrap items-center gap-2'>
      {value.length === 0 && (
        <span className='text-xs text-muted-foreground'>{placeholder}</span>
      )}

      {value.map((item, i) => (
        <div
          key={item}
          data-draggable-tag-index={i}
          draggable
          onDragStart={() => onDragStart(i)}
          onDragEnter={() => onDragEnter(i)}
          onDrop={onDrop}
          onDragEnd={onDragEnd}
          onDragOver={(e) => e.preventDefault()}
          className={`transition-opacity ${dragOver === i ? 'opacity-40' : 'opacity-100'}`}
        >
          <Badge
            variant='secondary'
            className='flex h-7 cursor-grab items-center gap-1 pr-1 pl-1.5 select-none active:cursor-grabbing'
          >
            <button
              type='button'
              aria-label={`拖拽排序 ${item}`}
              onClick={(event) => {
                event.preventDefault()
                event.stopPropagation()
              }}
              onTouchStart={onTouchStart(i)}
              onTouchMove={onTouchMove}
              onTouchEnd={onTouchEnd}
              onTouchCancel={onTouchEnd}
              className='flex shrink-0 touch-none items-center rounded-sm text-muted-foreground'
            >
              <GripVertical className='h-3 w-3' />
            </button>
            <span className='text-xs'>{item}</span>
            <button
              type='button'
              onClick={() => remove(item)}
              className='ml-0.5 rounded-full p-0.5 transition-colors hover:bg-muted-foreground/20'
            >
              <X className='h-3 w-3' />
            </button>
          </Badge>
        </div>
      ))}

      {available.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='h-7 gap-1 px-2 text-xs'
            >
              <Plus className='h-3 w-3' />
              {addLabel}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            {available.map((o) => (
              <DropdownMenuItem key={o} onClick={() => add(o)}>
                {o}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  )
}
