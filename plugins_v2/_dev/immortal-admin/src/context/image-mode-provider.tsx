import { createContext, useContext, useEffect, useState } from 'react'
import { getCookie, setCookie } from '@/lib/cookies'

export type ImageMode = 'show' | 'blur' | 'hide'
const DEFAULT_IMAGE_MODE = 'hide'
const IMAGE_CSS_NAME = 'data-image-mode'
const IMAGE_COOKIE_NAME = 'image-mode'

const ImageModeContext = createContext<{
  mode: ImageMode
  setMode: (m: ImageMode) => void
}>({
  mode: DEFAULT_IMAGE_MODE,
  setMode: () => {},
})

export function ImageModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ImageMode>(() => {
    const saved = getCookie(IMAGE_COOKIE_NAME)
    return (saved as ImageMode) || DEFAULT_IMAGE_MODE
  })

  useEffect(() => {
    setCookie(IMAGE_COOKIE_NAME, mode)
    document.body.setAttribute(IMAGE_CSS_NAME, mode)
  }, [mode])

  return (
    <ImageModeContext.Provider value={{ mode, setMode }}>
      <div data-image-mode={mode}>{children}</div>
    </ImageModeContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useImageMode = () => useContext(ImageModeContext)
