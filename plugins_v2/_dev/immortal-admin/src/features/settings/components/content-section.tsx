import type { JSX } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card.tsx'

type ContentSectionProps = {
  title: string
  desc: string
  children: React.JSX.Element
  icon: JSX.Element
}

export function ContentSection({
  title,
  desc,
  children,
  icon,
}: ContentSectionProps) {
  return (
    <Card className='space-y-4 mt-4 gap-2'>
      <CardHeader>
        <div className='flex items-center justify-between'>
          <div className='flex items-center gap-2'>
            <div className='rounded-lg bg-primary/10 p-2'>
              {icon}
            </div>
            <div>
              <CardTitle>{title}</CardTitle>
              <CardDescription>{desc}</CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className='space-y-4'>{children}</CardContent>
    </Card>
  )
}
