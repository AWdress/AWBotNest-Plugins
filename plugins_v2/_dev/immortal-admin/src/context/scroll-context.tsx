// ScrollContext.tsx
import { createContext, useContext, type RefObject } from 'react'

interface ScrollContextType {
  scrollContainerRef: RefObject<HTMLDivElement | null> | null
}

export const ScrollContext = createContext<ScrollContextType>({
  scrollContainerRef: null,
})

export const useScrollContainer = () => useContext(ScrollContext)