import { createContext, useContext, useEffect, useState } from 'react'
import { CommandMenu } from '@/components/command-menu'
import { useNavigate } from '@tanstack/react-router'

type SearchTarget = 'articles' | 'movie-search' | 'cast-search'

type SearchOptions = {
  target?: SearchTarget
}

type SearchContextType = {
  open: boolean
  setOpen: React.Dispatch<React.SetStateAction<boolean>>
  keyword: string
  setKeyword: (v: string) => void
  handleSearch: (value?: string, options?: SearchOptions) => void
}

const SearchContext = createContext<SearchContextType | null>(null)

type SearchProviderProps = {
  children: React.ReactNode
}

export function SearchProvider({ children }: SearchProviderProps) {
  const [open, setOpen] = useState(false)
  const [keyword, setKeyword] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((open) => !open)
      }
    }
    document.addEventListener('keydown', down)
    return () => document.removeEventListener('keydown', down)
  }, [])

  const handleSearch = (value?: string, options?: SearchOptions) => {
    const q = (value ?? keyword).trim()
    if (!q) return

    const target = options?.target ?? 'articles'
    setKeyword(q)
    setOpen(false)

    if (target === 'movie-search') {
      navigate({
        to: '/subscribes/search',
        search: {
          entity: 'movie',
          keyword: q,
        },
      })
      return
    }

    if (target === 'cast-search') {
      navigate({
        to: '/subscribes/search',
        search: {
          entity: 'cast',
          keyword: q,
        },
      })
      return
    }

    navigate({
      to: '/articles',
    })
  }

  return (
    <SearchContext value={{ open, setOpen, keyword, setKeyword, handleSearch }}>
      {children}
      <CommandMenu />
    </SearchContext>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useSearch = () => {
  const searchContext = useContext(SearchContext)

  if (!searchContext) {
    throw new Error('useSearch has to be used within SearchProvider')
  }

  return searchContext
}
