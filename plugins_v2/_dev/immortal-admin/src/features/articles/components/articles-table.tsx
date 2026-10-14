import { useEffect, useMemo, useState } from 'react'
import { addDays, format } from 'date-fns'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, Clock } from 'lucide-react'
import type { DateRange } from 'react-day-picker'
import {
  flattenSectionsByWebsite,
  getArticles,
  getCategories,
} from '@/api/article.ts'
import { formatDate } from '@/lib/utils.ts'
import { useSearch } from '@/context/search-provider.tsx'
import { useDebounce } from '@/hooks/use-debounce.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardHeader } from '@/components/ui/card.tsx'
import { Checkbox } from '@/components/ui/checkbox.tsx'
import { Input } from '@/components/ui/input.tsx'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.tsx'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table.tsx'
import { CommonPagination } from '@/components/pagination.tsx'
import { DownloaderDialog } from '@/features/articles/components/downloader-dialog.tsx'

export function ArticlesTable() {
  const { keyword: contextKeyword } = useSearch()
  const [keyword, setKeyword] = useState(contextKeyword)
  const [open, setOpen] = useState(false)
  const [articleIdList, setArticleIdList] = useState<number[]>([])
  const debouncedKeyword = useDebounce(keyword, 300)
  const [selectTids, setSelectTids] = useState<Set<number>>(new Set())
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: addDays(new Date(), -7),
    to: new Date(),
  })
  const [filter, setFilter] = useState({
    page: 1,
    page_size: 50,
    keyword: '',
    website: 'ALL',
    section: 'ALL',
    category: 'ALL',
    date_range: {
      from: '',
      to: '',
    },
  })

  const { data, isLoading } = useQuery({
    queryKey: [
      'articles',
      filter,
      dateRange?.from,
      dateRange?.to,
      debouncedKeyword,
    ],
    queryFn: async () => {
      const res = await getArticles({
        ...filter,
        keyword: debouncedKeyword,
        website: filter.website === 'ALL' ? '' : filter.website,
        section: filter.section === 'ALL' ? '' : filter.section,
        category: filter.category === 'ALL' ? '' : filter.category,
        date_range: {
          from: formatDate(dateRange?.from),
          to: formatDate(dateRange?.to),
        },
      })
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    setFilter((prev) => ({ ...prev, page: 1 }))
  }, [debouncedKeyword])

  const allIds = data?.items.map((item) => item.id) ?? []
  const isAllChecked =
    allIds.length > 0 && allIds.every((id) => selectTids.has(id))
  const isIndeterminate =
    allIds.some((id) => selectTids.has(id)) && !isAllChecked

  const { data: categoryTree } = useQuery({
    queryKey: ['categories'],
    queryFn: async () => {
      const res = await getCategories()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const websiteOptions = useMemo(
    () =>
      [{ value: 'ALL', label: '全部网站' }].concat(
        (categoryTree ?? []).map((item) => ({
          value: item.name,
          label: item.name,
        }))
      ),
    [categoryTree]
  )

  const sections = useMemo(
    () =>
      flattenSectionsByWebsite(
        categoryTree ?? [],
        filter.website === 'ALL' ? undefined : filter.website
      ),
    [categoryTree, filter.website]
  )

  const categories = useMemo(
    () =>
      sections.find((item) => item.name === filter.section)?.categories ?? [],
    [filter.section, sections]
  )

  useEffect(() => {
    const sectionNames = new Set((sections ?? []).map((item) => item.name))
    if (filter.section !== 'ALL' && !sectionNames.has(filter.section)) {
      setFilter((prev) => ({
        ...prev,
        section: 'ALL',
        category: 'ALL',
        page: 1,
      }))
      return
    }

    const categoryNames = new Set(categories.map((item) => item.name))
    if (filter.category !== 'ALL' && !categoryNames.has(filter.category)) {
      setFilter((prev) => ({ ...prev, category: 'ALL', page: 1 }))
    }
  }, [categories, filter.category, filter.section, sections])

  return (
    <div className='flex h-full flex-col space-y-2 overflow-hidden'>
      <div className='shrink-0'>
        <Card className='w-full'>
          <CardHeader>筛选条件</CardHeader>
          <CardContent className='grid grid-cols-1 gap-4 md:grid-cols-4'>
            <Select
              value={filter.website}
              onValueChange={(value) =>
                setFilter((prev) => ({
                  ...prev,
                  website: value,
                  section: 'ALL',
                  category: 'ALL',
                  page: 1,
                }))
              }
            >
              <SelectTrigger className='w-full'>
                <SelectValue placeholder='网站' />
              </SelectTrigger>
              <SelectContent className='w-full'>
                {websiteOptions.map((item) => (
                  <SelectItem key={item.value} value={item.value}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={filter.section}
              onValueChange={(value) =>
                setFilter((prev) => ({
                  ...prev,
                  section: value,
                  category: 'ALL',
                  page: 1,
                }))
              }
            >
              <SelectTrigger className='w-full'>
                <SelectValue placeholder='板块' />
              </SelectTrigger>
              <SelectContent className='w-full'>
                <SelectItem value='ALL'>不限板块</SelectItem>
                {sections?.map((item) => (
                  <SelectItem key={item.name} value={item.name}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={filter.category}
              onValueChange={(value) =>
                setFilter((prev) => ({ ...prev, category: value, page: 1 }))
              }
            >
              <SelectTrigger className='w-full'>
                <SelectValue placeholder='分类' />
              </SelectTrigger>
              <SelectContent className='w-full'>
                <SelectItem value='ALL'>不限分类</SelectItem>
                {categories.map((item) => (
                  <SelectItem key={item.name} value={item.name}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Input
              placeholder='关键词'
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />

            <div className='flex items-center gap-2'>
              <Input
                type='date'
                max={
                  dateRange?.to
                    ? format(dateRange.to, 'yyyy-MM-dd')
                    : format(new Date(), 'yyyy-MM-dd')
                }
                value={
                  dateRange?.from ? format(dateRange.from, 'yyyy-MM-dd') : ''
                }
                onChange={(e) =>
                  setDateRange((prev) => ({
                    from: e.target.value ? new Date(e.target.value) : undefined,
                    to: prev?.to,
                  }))
                }
                className='w-36'
              />
              <span className='text-muted-foreground'>~</span>
              <Input
                type='date'
                min={
                  dateRange?.from ? format(dateRange.from, 'yyyy-MM-dd') : ''
                }
                max={format(new Date(), 'yyyy-MM-dd')}
                value={dateRange?.to ? format(dateRange.to, 'yyyy-MM-dd') : ''}
                onChange={(e) =>
                  setDateRange((prev) => ({
                    from: prev?.from,
                    to: e.target.value ? new Date(e.target.value) : undefined,
                  }))
                }
                className='w-36'
              />
            </div>

            <div className='flex gap-2'>
              <Button
                variant='destructive'
                onClick={() => {
                  setOpen(true)
                  setArticleIdList([...selectTids])
                }}
              >
                批量下载
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className='flex-1 overflow-auto rounded-lg border'>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <Checkbox
                  checked={
                    isAllChecked
                      ? true
                      : isIndeterminate
                        ? 'indeterminate'
                        : false
                  }
                  onCheckedChange={(checked) => {
                    setSelectTids((prev) => {
                      const next = new Set(prev)
                      if (checked) {
                        allIds.forEach((id) => next.add(id))
                      } else {
                        allIds.forEach((id) => next.delete(id))
                      }
                      return next
                    })
                  }}
                />
              </TableHead>
              <TableHead>ID</TableHead>
              <TableHead>网站</TableHead>
              <TableHead>板块</TableHead>
              <TableHead>分类</TableHead>
              <TableHead>标题</TableHead>
              <TableHead>大小</TableHead>
              <TableHead>发布日期</TableHead>
              <TableHead>下载状态</TableHead>
            </TableRow>
          </TableHeader>

          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={9} className='text-center'>
                  加载中...
                </TableCell>
              </TableRow>
            ) : data?.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} className='text-center'>
                  暂无数据
                </TableCell>
              </TableRow>
            ) : (
              (data?.items ?? []).map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <Checkbox
                      checked={selectTids.has(item.id)}
                      onCheckedChange={(checked) => {
                        setSelectTids((prev) => {
                          const next = new Set(prev)
                          if (checked) {
                            next.add(item.id)
                          } else {
                            next.delete(item.id)
                          }
                          return next
                        })
                      }}
                    />
                  </TableCell>
                  <TableCell>{item.id}</TableCell>
                  <TableCell>{item.website}</TableCell>
                  <TableCell>{item.section}</TableCell>
                  <TableCell>{item.category}</TableCell>
                  <TableCell>{item.title}</TableCell>
                  <TableCell>{item.size}mb</TableCell>
                  <TableCell>{item.publish_date}</TableCell>
                  <TableCell className='flex gap-1'>
                    <span
                      className={`flex items-center gap-1 rounded-full px-2.5 py-1 font-medium ${
                        item.in_stock
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
                      }`}
                    >
                      {item.in_stock ? (
                        <>
                          <CheckCircle2 className='h-3 w-3' />
                          已下载
                        </>
                      ) : (
                        <>
                          <Clock className='h-3 w-3' />
                          未下载
                        </>
                      )}
                    </span>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
      <DownloaderDialog
        articleIdList={articleIdList}
        open={open}
        onOpenChange={setOpen}
      />
      <div className='shrink-0'>
        <CommonPagination
          page={filter.page}
          total={data?.total || 0}
          pageSize={filter.page_size}
          onChange={(v) => setFilter((prev) => ({ ...prev, page: v }))}
        />
      </div>
    </div>
  )
}
