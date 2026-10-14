import { cn } from '@/lib/utils'

type MainProps = React.HTMLAttributes<HTMLElement> & {
  fixed?: boolean
  fluid?: boolean
  ref?: React.Ref<HTMLElement>
}

export function Main({ fixed, className, fluid, children, ...props }: MainProps) {
  return (
    <main
      data-layout={fixed ? 'fixed' : 'auto'}
      className={cn(
        'relative px-4',
        fixed && 'flex grow flex-col overflow-hidden',
        !fluid && '@7xl/content:w-full',
        className
      )}
      {...props}
    >
      {children}
    </main>
  )
}
