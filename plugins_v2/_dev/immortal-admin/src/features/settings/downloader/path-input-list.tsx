import { HelpCircle, Plus, Trash2 } from 'lucide-react'
import type { SavePath } from '@/api/config.ts'
import { Button } from '@/components/ui/button.tsx'
import { Input } from '@/components/ui/input.tsx'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover.tsx'

export function PathListInput({
  value,
  onChange,
}: {
  value: SavePath[]
  onChange: (v: SavePath[]) => void
}) {
  const addPath = () => onChange([...value, { label: '', path: '' }])

  const updateItem = (index: number, key: 'label' | 'path', val: string) => {
    onChange(
      value.map((item, i) => (i == index ? { ...item, [key]: val } : item))
    )
  }

  const removePath = (index: number) => {
    onChange(value.filter((_item, i) => i !== index))
  }

  return (
    <div className='space-y-2'>
      {value.map((item, index) => (
        <div key={index} className='grid grid-cols-11 gap-2'>
          <Input
            className='col-span-5'
            placeholder='名称（如：电影）'
            value={item.label}
            onChange={(e) => updateItem(index, 'label', e.target.value)}
          />
          <Input
            className='col-span-5'
            placeholder='/downloads/movie,fileid'
            value={item.path}
            onChange={(e) => updateItem(index, 'path', e.target.value)}
          />
          <Button
            size='icon'
            variant='ghost'
            className='text-destructive'
            onClick={() => removePath(index)}
          >
            <Trash2 />
          </Button>
        </div>
      ))}

      <div className='flex justify-between gap-2'>
        <Button variant='outline' onClick={addPath}>
          <Plus className='mr-2 h-4 w-4' />
          添加目录
        </Button>
        <Popover>
          <PopoverTrigger asChild>
            <button className='flex items-center gap-1 text-xs text-primary hover:underline'>
              <HelpCircle className='h-3 w-3' />
              动态目录
            </button>
          </PopoverTrigger>

          <PopoverContent className='text-sm bg-background/20 backdrop-blur-lg' align='start'>
            <div className='space-y-2'>
              <p className='font-medium'>如何使用动态目录</p>
              支持动态目录，可用参数：
              <p className='rounded bg-muted px-1 py-0.5 text-foreground'>
                {'{section}'}（板块）
              </p>
              <p className='rounded bg-muted px-1 py-0.5 text-foreground'>
                {'{category}'}（分类）
              </p>
              <p className='rounded bg-muted px-1 py-0.5 text-foreground'>
                {'{publish_date}'}（发布日期）
              </p>
              <p className='rounded bg-muted px-1 py-0.5 text-foreground'>
                {'{current_date}'}（当前日期）
              </p>
              <br />
              示例：
              <p className='rounded bg-muted px-1 py-0.5 text-foreground'>
                /115open/{'{section}'}/{'{category}'}
              </p>
            </div>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  )
}
