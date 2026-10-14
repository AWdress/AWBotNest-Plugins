import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { Loader2, ArrowUp } from 'lucide-react'
import { type Article, flattenSectionsByWebsite, getArticles, getCategories } from '@/api/article.ts'
import { useSearch } from '@/context/search-provider.tsx'
import { useDebounce } from '@/hooks/use-debounce.tsx'
import { ImagePreview } from '@/components/image-preview.tsx'
import { ArticleCard } from '@/features/articles/components/article-card.tsx'
import { DownloaderDialog } from '@/features/articles/components/downloader-dialog.tsx'
import { FilterBar } from '@/features/articles/components/filter-bar.tsx'

export function ArticlesMobile() {
  const { keyword } = useSearch()
  const [open, setOpen] = useState(false)
  const [articleIdList, setArticleIdList] = useState<number[]>([])
  const [previewImages, setPreviewImages] = useState<string[]>([])
  const [imgPreviewOpen, setImgPreviewOpen] = useState(false)
  const [alt, setAlt] = useState('')
  const [previewArticleIndex, setPreviewArticleIndex] = useState<number | null>(null)
  const [pendingPreviewNextFetch, setPendingPreviewNextFetch] = useState(false)
  const [showBackToTop, setShowBackToTop] = useState(false)
  const debouncedKeyword = useDebounce(keyword, 300)
  const [filter, setFilter] = useState({
    page: 1,
    page_size: 10,
    keyword: '',
    website: '',
    section: '',
    category: '',
    date_range: {
      from: '',
      to: '',
    },
  })

  const loadMoreRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const cardRefs = useRef<(HTMLDivElement | null)[]>([])

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading } =
    useInfiniteQuery({
      queryKey: ['articles-infinite', filter, debouncedKeyword],
      queryFn: async ({ pageParam = 1 }) => {
        const res = await getArticles({
          ...filter,
          page: pageParam,
          keyword: debouncedKeyword,
        })
        return res.data
      },
      getNextPageParam: (lastPage) => {
        return lastPage.hasMore ? lastPage.page + 1 : undefined
      },
      initialPageParam: 1,
      staleTime: 5 * 60 * 1000,
    })

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFilter((prev) => ({ ...prev, page: 1 }))
  }, [debouncedKeyword])

  const { data: categoryTree } = useQuery({
    queryKey: ['category'],
    queryFn: async () => {
      const res = await getCategories()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const categories = useMemo(() => flattenSectionsByWebsite(categoryTree ?? []), [categoryTree])

  // 监听滚动显示/隐藏回到顶部按钮
  useEffect(() => {
    const scrollContainer = scrollContainerRef.current
    if (!scrollContainer) return

    const handleScroll = () => {
      setShowBackToTop(scrollContainer.scrollTop > 300)
    }

    scrollContainer.addEventListener('scroll', handleScroll)
    return () => scrollContainer.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    if (!loadMoreRef.current) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      {
        root: null,
        rootMargin: '100px',
      }
    )
    observer.observe(loadMoreRef.current)
    return () => observer.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage])

  const scrollToTop = () => {
    scrollContainerRef.current?.scrollTo({
      top: 0,
      behavior: 'smooth',
    })
  }

  const articles = data?.pages.flatMap((page) => page.items) || []
  const total = data?.pages[0]?.total || 0

  const openPreview = (article: Article, index: number) => {
    setPreviewImages(article.img_list.filter(Boolean))
    setAlt(article.title)
    setPreviewArticleIndex(index)
    setImgPreviewOpen(true)
  }

  const closePreview = () => {
    setImgPreviewOpen(false)
    setAlt('')
    setPreviewImages([])
    setPreviewArticleIndex(null)
    setPendingPreviewNextFetch(false)
  }

  const switchPreviewArticle = useCallback((nextIndex: number) => {
    const article = articles[nextIndex]
    if (!article) {
      return
    }
    setPreviewImages(article.img_list.filter(Boolean))
    setAlt(article.title)
    setPreviewArticleIndex(nextIndex)
    const card = cardRefs.current[nextIndex]
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [articles])

  useEffect(() => {
    if (!pendingPreviewNextFetch || isFetchingNextPage) {
      return
    }

    if (previewArticleIndex === null) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPendingPreviewNextFetch(false)
      return
    }

    if (previewArticleIndex < articles.length - 1) {
      switchPreviewArticle(previewArticleIndex + 1)
    }

    setPendingPreviewNextFetch(false)
  }, [articles, isFetchingNextPage, pendingPreviewNextFetch, previewArticleIndex, switchPreviewArticle])

  const goToPrevPreviewArticle = () => {
    if (previewArticleIndex === null || previewArticleIndex <= 0) {
      return
    }
    switchPreviewArticle(previewArticleIndex - 1)
  }

  const goToNextPreviewArticle = async () => {
    if (previewArticleIndex === null) {
      return
    }

    if (previewArticleIndex < articles.length - 1) {
      switchPreviewArticle(previewArticleIndex + 1)
      return
    }

    if (!hasNextPage || isFetchingNextPage || pendingPreviewNextFetch) {
      return
    }

    setPendingPreviewNextFetch(true)
    await fetchNextPage()
  }

  const hasPrevPreviewArticle = previewArticleIndex !== null && previewArticleIndex > 0
  const hasNextPreviewArticle =
    previewArticleIndex !== null &&
    (previewArticleIndex < articles.length - 1 || hasNextPage || pendingPreviewNextFetch)
  const isSwitchingPreviewArticle = isFetchingNextPage && pendingPreviewNextFetch

  return (
    <div className='flex flex-col overflow-hidden -mx-4  md:mx-0 md:w-full'>
      <div className='shrink-0'>
        <FilterBar
          value={filter}
          categories={categories || []}
          onChange={(v) => setFilter(v)}
        />
      </div>
      <div ref={scrollContainerRef} className='flex-1 overflow-auto scrollbar-hide' data-main-scroll-container>
        <div className='grid gap-2'>
          {articles.map((article, index) => (
            <div key={article.id} ref={(el) => { cardRefs.current[index] = el }}>
              <ArticleCard
                article={article}
                onImgClick={() => openPreview(article, index)}
                onDownload={() => {
                  setOpen(true)
                  setArticleIdList([article.id])
                }}
              />
            </div>
          ))}
        </div>
        <ImagePreview
          images={previewImages}
          alt={alt}
          open={imgPreviewOpen}
          onClose={closePreview}
          onPrevArticle={goToPrevPreviewArticle}
          onNextArticle={goToNextPreviewArticle}
          hasPrevArticle={hasPrevPreviewArticle}
          hasNextArticle={hasNextPreviewArticle}
        ></ImagePreview>
        {isSwitchingPreviewArticle && (
          <div className='px-4 pb-2 text-center text-sm text-muted-foreground'>
            正在加载下一篇...
          </div>
        )}
        <DownloaderDialog
          articleIdList={articleIdList}
          open={open}
          onOpenChange={setOpen}
        ></DownloaderDialog>

        <div ref={loadMoreRef} className='py-4 text-center'>
          {isFetchingNextPage && (
            <div className='flex items-center justify-center gap-2 text-muted-foreground'>
              <Loader2 className='h-5 w-5 animate-spin' />
              <span>加载中...</span>
            </div>
          )}
          {!hasNextPage && articles.length > 0 && (
            <div className='text-sm text-muted-foreground'>
              已加载全部 {total} 条数据
            </div>
          )}
        </div>

        {isLoading && (
          <div className='flex items-center justify-center py-8'>
            <Loader2 className='h-6 w-6 animate-spin text-muted-foreground' />
          </div>
        )}
      </div>

      {/* 回到顶部按钮 */}
      <button
        className={`fixed bottom-[calc(90px+env(safe-area-inset-bottom))] right-4 z-40 flex h-11 w-11 items-center justify-center rounded-full bg-linear-to-br from-primary/90 to-primary shadow-lg backdrop-blur-sm transition-all duration-300 hover:scale-110 hover:shadow-xl active:scale-95 ${
          showBackToTop
            ? 'translate-y-0 opacity-100'
            : 'pointer-events-none translate-y-16 opacity-0'
        }`}
        onClick={scrollToTop}
        aria-label='回到顶部'
      >
        <ArrowUp className='h-5 w-5 text-primary-foreground' />
      </button>
    </div>
  )
}