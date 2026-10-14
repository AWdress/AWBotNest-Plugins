import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function sleep(ms: number = 1000) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function getPageNumbers(currentPage: number, totalPages: number) {
  const maxVisiblePages = 5 // Maximum number of page buttons to show
  const rangeWithDots = []

  if (totalPages <= maxVisiblePages) {
    for (let i = 1; i <= totalPages; i++) {
      rangeWithDots.push(i)
    }
  } else {
    rangeWithDots.push(1)

    if (currentPage <= 3) {
      for (let i = 2; i <= 4; i++) {
        rangeWithDots.push(i)
      }
      rangeWithDots.push('...', totalPages)
    } else if (currentPage >= totalPages - 2) {
      rangeWithDots.push('...')
      for (let i = totalPages - 3; i <= totalPages; i++) {
        rangeWithDots.push(i)
      }
    } else {
      rangeWithDots.push('...')
      for (let i = currentPage - 1; i <= currentPage + 1; i++) {
        rangeWithDots.push(i)
      }
      rangeWithDots.push('...', totalPages)
    }
  }

  return rangeWithDots
}

export function formatDate(date?: Date) {
  if (!date) return ''
  return date.toISOString().slice(0, 10)
}

export function formatDateTime(isoString: string) {
  const date = new Date(isoString)

  const pad = (n: number) => String(n).padStart(2, '0')

  const Y = date.getFullYear()
  const M = pad(date.getMonth() + 1)
  const D = pad(date.getDate())
  const h = pad(date.getHours())
  const m = pad(date.getMinutes())
  const s = pad(date.getSeconds())

  return `${Y}-${M}-${D} ${h}:${m}:${s}`
}


/**
 * 将 OKLCH 颜色转换为 HEX
 * @param l - Lightness (0-1)
 * @param c - Chroma (0-0.4)
 * @param h - Hue (0-360)
 * @returns HEX 颜色字符串
 */
export function oklchToHex(l: number, c: number, h: number): string {
  // OKLCH -> OKLAB
  const a = c * Math.cos((h * Math.PI) / 180)
  const t = c * Math.sin((h * Math.PI) / 180)

  // OKLAB -> Linear RGB
  const l_ = l + 0.3963377774 * a + 0.2158037573 * t
  const m_ = l - 0.1055613458 * a - 0.0638541728 * t
  const s_ = l - 0.0894841775 * a - 1.291485548 * t

  const l3 = l_ * l_ * l_
  const m3 = m_ * m_ * m_
  const s3 = s_ * s_ * s_

  const r_linear = +4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
  const g_linear = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
  const b_linear = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.707614701 * s3

  // Linear RGB -> sRGB
  const toSRGB = (val: number): number => {
    const abs = Math.abs(val)
    if (abs <= 0.0031308) {
      return val * 12.92
    }
    return (Math.sign(val) * 1.055 * Math.pow(abs, 1 / 2.4) - 0.055)
  }

  const r = toSRGB(r_linear)
  const g = toSRGB(g_linear)
  const b = toSRGB(b_linear)

  // sRGB -> 8-bit RGB
  const to8Bit = (val: number): number => {
    return Math.max(0, Math.min(255, Math.round(val * 255)))
  }

  const r8 = to8Bit(r)
  const g8 = to8Bit(g)
  const b8 = to8Bit(b)

  // RGB -> HEX
  return `#${r8.toString(16).padStart(2, '0')}${g8.toString(16).padStart(2, '0')}${b8.toString(16).padStart(2, '0')}`
}

/**
 * 从 CSS OKLCH 字符串解析并转换为 HEX
 * @param oklchString - 例如 "oklch(0.129 0.042 264.695)"
 * @returns HEX 颜色字符串
 */
export function parseOklchToHex(oklchString: string): string {
  const match = oklchString.match(/oklch\(([\d.]+)\s+([\d.]+)\s+([\d.]+)\)/)
  if (!match) {
    throw new Error(`Invalid OKLCH string: ${oklchString}`)
  }

  const [, l, c, h] = match.map(Number)
  return oklchToHex(l, c, h)
}