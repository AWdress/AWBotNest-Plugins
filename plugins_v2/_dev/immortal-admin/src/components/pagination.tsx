import { useEffect, useState } from 'react'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from 'lucide-react'
import { getPageNumbers } from '@/lib/utils.ts'
import { Button } from '@/components/ui/button.tsx'
import { Input } from '@/components/ui/input.tsx'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
} from '@/components/ui/pagination.tsx'

interface Props {
  page: number
  total: number
  pageSize: number
  onChange: (page: number) => void
}

export function CommonPagination({ page, total, pageSize, onChange }: Props) {
  const totalPages = Math.ceil(total / pageSize)
  const pages = getPageNumbers(page, totalPages)
  const [jumpPage, setJumpPage] = useState(String(page))

  useEffect(() => {
    setJumpPage(String(page))
  }, [page])

  if (totalPages <= 1) return null

  const handleJump = () => {
    const nextPage = Number.parseInt(jumpPage, 10)
    if (Number.isNaN(nextPage)) {
      setJumpPage(String(page))
      return
    }

    const normalizedPage = Math.min(totalPages, Math.max(1, nextPage))
    setJumpPage(String(normalizedPage))
    if (normalizedPage !== page) {
      onChange(normalizedPage)
    }
  }

  return (
    <div className='flex flex-nowrap items-center justify-between gap-3'>
      <Pagination className='min-w-0 flex-1 justify-start'>
        <PaginationContent className='flex-nowrap gap-2'>
          <PaginationItem>
            <PaginationLink
              className='h-8 min-w-8 cursor-pointer px-1'
              onClick={() => onChange(1)}
              aria-disabled={page === 1}
            >
              <ChevronsLeftIcon />
            </PaginationLink>
          </PaginationItem>

          <PaginationItem>
            <PaginationLink
              className='h-8 min-w-8 cursor-pointer px-1'
              onClick={() => onChange(Math.max(1, page - 1))}
              aria-disabled={page === 1}
            >
              <ChevronLeftIcon />
            </PaginationLink>
          </PaginationItem>

          {pages.map((p, i) => (
            <PaginationItem key={i}>
              {p === '...' ? (
                <span className='px-3 text-muted-foreground'>…</span>
              ) : (
                <PaginationLink
                  className='h-8 min-w-8 cursor-pointer px-1'
                  isActive={p === page}
                  onClick={() => onChange(p as number)}
                >
                  {p}
                </PaginationLink>
              )}
            </PaginationItem>
          ))}

          <PaginationItem>
            <PaginationLink
              className='h-8 min-w-8 cursor-pointer px-1'
              onClick={() => onChange(Math.min(totalPages, page + 1))}
              aria-disabled={page === totalPages}
            >
              <ChevronRightIcon />
            </PaginationLink>
          </PaginationItem>

          <PaginationItem>
            <PaginationLink
              className='h-8 min-w-8 cursor-pointer px-1'
              onClick={() => onChange(totalPages)}
              aria-disabled={page === totalPages}
            >
              <ChevronsRightIcon />
            </PaginationLink>
          </PaginationItem>
        </PaginationContent>
      </Pagination>

      <div className='flex shrink-0 items-center gap-2 text-sm text-muted-foreground'>
        <span>跳转到</span>
        <Input
          value={jumpPage}
          onChange={(event) =>
            setJumpPage(event.target.value.replace(/[^\d]/g, ''))
          }
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              handleJump()
            }
          }}
          inputMode='numeric'
          className='h-8 w-20 text-center'
        />
        <span>页</span>
        <Button type='button' variant='outline' size='sm' onClick={handleJump}>
          前往
        </Button>
      </div>
    </div>
  )
}
