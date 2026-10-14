import type { JSX } from 'react'

export function ContentTitle({
  title,
  description,
  icon,
}: {
  title?: string
  description?: string
  icon?: JSX.Element
}) {
  return (
    <div className='mb-2 flex flex-wrap items-end justify-between gap-2'>
      <div>
        <div className='mb-2 flex items-center gap-3'>
          {icon}
          <h2 className='text-2xl font-bold tracking-tight'>{title}</h2>
        </div>
        <p className='text-sm text-muted-foreground'>{description}</p>
      </div>
    </div>
  )
}
