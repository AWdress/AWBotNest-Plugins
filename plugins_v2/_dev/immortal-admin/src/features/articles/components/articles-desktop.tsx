import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { type Article, flattenSectionsByWebsite, getArticles, getCategories } from '@/api/article.ts'
import { useSearch } from '@/context/search-provider.tsx'
import { useDebounce } from '@/hooks/use-debounce.tsx'
import { EmptyState } from '@/components/empty.tsx'
import { ImagePreview } from '@/components/image-preview.tsx'
import { Loading } from '@/components/loading.tsx'
import { CommonPagination } from '@/components/pagination.tsx'
import { ArticleCard } from '@/features/articles/components/article-card.tsx'
import { DownloaderDialog } from '@/features/articles/components/downloader-dialog.tsx'
import { FilterBar } from '@/features/articles/components/filter-bar.tsx'

export function ArticlesDesktop() {
  const { keyword } = useSearch()
  const debouncedKeyword = useDebounce(keyword, 300)
  const [open, setOpen] = useState(false)
  const [articleIdList, setArticleIdList] = useState<number[]>([])
  const [filter, setFilter] = useState({
    page: 1,
    page_size: 36,
    keyword: '',
    website: '',
    section: '',
    category: '',
    date_range: {
      from: '',
      to: '',
    },
  })
  const [previewImages, setPreviewImages] = useState<string[]>([])
  const [imgPreviewOpen, setImgPreviewOpen] = useState(false)
  const [alt, setAlt] = useState('')
  const [previewArticleIndex, setPreviewArticleIndex] = useState<number | null>(null)
  const [pendingPreviewPageSwitch, setPendingPreviewPageSwitch] = useState<{
    direction: 'prev' | 'next'
    targetPage: number
  } | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['articles', filter, debouncedKeyword],
    queryFn: async () => {
      const res = await getArticles({ ...filter, keyword: debouncedKeyword })
      return res.data
    },
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
  const previewArticles = data?.items ?? []

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
    setPendingPreviewPageSwitch(null)
  }

  const switchPreviewArticle = (nextIndex: number) => {
    const article = previewArticles[nextIndex]
    if (!article) {
      return
    }
    setPreviewImages(article.img_list.filter(Boolean))
    setAlt(article.title)
    setPreviewArticleIndex(nextIndex)
  }

  useEffect(() => {
    if (!pendingPreviewPageSwitch || isLoading) {
      return
    }

    if (filter.page !== pendingPreviewPageSwitch.targetPage) {
      return
    }

    if (previewArticles.length === 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPendingPreviewPageSwitch(null)
      return
    }

    const nextIndex = pendingPreviewPageSwitch.direction === 'next' ? 0 : previewArticles.length - 1
    switchPreviewArticle(nextIndex)
    setPendingPreviewPageSwitch(null)
  }, [filter.page, isLoading, pendingPreviewPageSwitch, previewArticles, switchPreviewArticle])

  const canSwitchToPrevPage = filter.page > 1
  const canSwitchToNextPage =
    data !== undefined && filter.page * filter.page_size < data.total

  const goToPrevPreviewArticle = () => {
    if (previewArticleIndex === null) {
      return
    }

    if (previewArticleIndex > 0) {
      switchPreviewArticle(previewArticleIndex - 1)
      return
    }

    if (!canSwitchToPrevPage) {
      return
    }

    const targetPage = filter.page - 1
    setPendingPreviewPageSwitch({ direction: 'prev', targetPage })
    setFilter((prev) => ({ ...prev, page: targetPage }))
  }

  const goToNextPreviewArticle = () => {
    if (previewArticleIndex === null) {
      return
    }

    if (previewArticleIndex < previewArticles.length - 1) {
      switchPreviewArticle(previewArticleIndex + 1)
      return
    }

    if (!canSwitchToNextPage) {
      return
    }

    const targetPage = filter.page + 1
    setPendingPreviewPageSwitch({ direction: 'next', targetPage })
    setFilter((prev) => ({ ...prev, page: targetPage }))
  }

  return (
    <div className='flex h-full flex-col overflow-hidden space-y-2'>
      {/* 鈶?绛涢€夋爮 */}
      <div className='shrink-0'>
        <FilterBar
          value={filter}
          categories={categories || []}
          onChange={(v) => setFilter(v)}
        />
      </div>

      <div className='flex-1 overflow-auto'>
        {isLoading && <Loading />}
        {data?.items.length === 0 && <EmptyState />}
        <div className='grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6'>
          {data?.items.map((article, index) => (
            <ArticleCard
              key={article.id}
              article={article}
              onImgClick={() => openPreview(article, index)}
              onDownload={() => {
                setOpen(true)
                setArticleIdList([article.id])
              }}
            />
          ))}
        </div>
      </div>
      <ImagePreview
        images={previewImages}
        alt={alt}
        open={imgPreviewOpen}
        onClose={closePreview}
        onPrevArticle={goToPrevPreviewArticle}
        onNextArticle={goToNextPreviewArticle}
        hasPrevArticle={
          previewArticleIndex !== null &&
          (previewArticleIndex > 0 || canSwitchToPrevPage)
        }
        hasNextArticle={
          previewArticleIndex !== null &&
          (previewArticleIndex < previewArticles.length - 1 || canSwitchToNextPage)
        }
      ></ImagePreview>
      <DownloaderDialog
        articleIdList={articleIdList}
        open={open}
        onOpenChange={setOpen}
      ></DownloaderDialog>

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
