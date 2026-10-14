import { Button } from '@/components/ui/button'
import { Eye, EyeOff, ScanEye } from 'lucide-react'
import { useImageMode } from '@/context/image-mode-provider'

const modes = ['show', 'blur', 'hide'] as const

const modeConfig = {
  show: { label: '显示图片', icon: Eye },
  blur: { label: '模糊图片', icon: ScanEye },
  hide: { label: '隐藏图片', icon: EyeOff },
} as const

export function ImageModeSwitch() {
  const { mode, setMode } = useImageMode()

  const currentIndex = modes.indexOf(mode)
  const nextMode = modes[(currentIndex + 1) % modes.length]

  const { label, icon: Icon } = modeConfig[mode]

  const toggleMode = () => {
    setMode(nextMode)
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      title={label}
      aria-label={label}
      onClick={toggleMode}
    >
      <Icon className="h-5 w-5" />
    </Button>
  )
}
