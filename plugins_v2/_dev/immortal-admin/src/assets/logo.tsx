import { type SVGProps, useId } from 'react'
import { cn } from '@/lib/utils'

type LogoProps = SVGProps<SVGSVGElement> & {
  title?: string
}

export function Logo({ className, title = '青灯不灭', ...props }: LogoProps) {
  const id = useId()
  const jadeId = `${id}-jade`
  const goldId = `${id}-gold`
  const stemId = `${id}-stem`

  return (
    <svg
      viewBox='0 0 256 256'
      xmlns='http://www.w3.org/2000/svg'
      aria-hidden={title ? undefined : true}
      role='img'
      className={cn('size-6 shrink-0', className)}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      <defs>
        <linearGradient id={jadeId} x1='92' y1='34' x2='164' y2='214' gradientUnits='userSpaceOnUse'>
          <stop stopColor='#94C6A7' />
          <stop offset='1' stopColor='#3C745D' />
        </linearGradient>
        <linearGradient id={goldId} x1='87' y1='31' x2='176' y2='211' gradientUnits='userSpaceOnUse'>
          <stop stopColor='#E4C97F' />
          <stop offset='0.45' stopColor='#C49B52' />
          <stop offset='1' stopColor='#8B672F' />
        </linearGradient>
        <linearGradient id={stemId} x1='130' y1='8' x2='148' y2='44' gradientUnits='userSpaceOnUse'>
          <stop stopColor='#426853' />
          <stop offset='1' stopColor='#173428' />
        </linearGradient>
      </defs>
      <g transform='translate(128 40) scale(1.2) translate(-128 -40)'>
        <path
          d='M129 30C145 30 158 44 158 60C158 73 152 84 143 91C165 101 181 123 181 151C181 187 156 213 123 213C90 213 65 187 65 151C65 123 81 101 103 91C94 84 88 73 88 60C88 44 101 30 117 30C123 30 127 34 129 39C132 34 137 30 144 30H129Z'
          fill={`url(#${jadeId})`}
          stroke={`url(#${goldId})`}
          strokeWidth='7'
          strokeLinejoin='round'
        />
        <path
          d='M127 22C127 11 136 7 148 7C145 18 141 26 133 33'
          fill='none'
          stroke={`url(#${stemId})`}
          strokeWidth='8'
          strokeLinecap='round'
          strokeLinejoin='round'
        />
        <path
          d='M129 43C137 43 143 48 143 56C143 64 137 69 129 69C121 69 115 64 115 56C115 48 121 43 129 43Z'
          fill='none'
          stroke='#E8D39A'
          strokeWidth='3'
          opacity='0.75'
        />
        <path
          d='M98 100C107 104 117 106 129 106C141 106 151 104 160 100'
          fill='none'
          stroke='#E8D39A'
          strokeWidth='3.2'
          strokeLinecap='round'
          opacity='0.72'
        />
        <path
          d='M91 148C103 143 116 141 130 141C144 141 157 143 169 148'
          fill='none'
          stroke='#E8D39A'
          strokeWidth='3.2'
          strokeLinecap='round'
          opacity='0.72'
        />
        <path
          d='M99 185C108 182 118 180 129 180C140 180 150 182 159 185'
          fill='none'
          stroke='#E8D39A'
          strokeWidth='3.2'
          strokeLinecap='round'
          opacity='0.72'
        />
      </g>
    </svg>
  )
}
