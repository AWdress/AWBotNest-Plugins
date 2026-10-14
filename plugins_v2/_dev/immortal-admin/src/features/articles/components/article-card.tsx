import { useState } from 'react'
import {
  Copy,
  Image as ImageIcon,
  Package,
  Calendar as CalendarIcon,
  CheckCircle2,
  Download,
  MoreVertical,
} from 'lucide-react'
import { toast } from 'sonner'
import type { Article } from '@/api/article.ts'
import { useImageMode } from '@/context/image-mode-provider.tsx'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { LazyImage } from '@/components/lazy-image'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function ArticleCard({
  article,
  onImgClick,
  onDownload,
}: {
  article: Article
  onImgClick?: () => void
  onDownload: () => void
}) {
  const { mode } = useImageMode()
  const images = (article.img_list ?? '').filter(Boolean)
  const [imageError, setImageError] = useState(false)

  const copyTextFallback = (text: string) => {
    const textarea = document.createElement('textarea')
    textarea.value = text

    // 防止页面跳动
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'

    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()

    const success = document.execCommand('copy')
    document.body.removeChild(textarea)

    return success
  }

  const handleCopyMagnet = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(article.magnet.join('\n'))
      } else {
        const ok = copyTextFallback(article.magnet.join('\n'))
        if (!ok) throw new Error('execCommand failed')
      }
      toast.success('磁力链接已复制')
    } catch (err) {
      toast.error(`复制失败:${err}`)
    }
  }

  const handleCopyEd2k = async () => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(article.edk.join('\n'))
      } else {
        const ok = copyTextFallback(article.edk.join('\n'))
        if (!ok) throw new Error('execCommand failed')
      }
      toast.success('Ed2k已复制')
    } catch (err) {
      toast.error(`复制失败:${err}`)
    }
  }

  return (
    <Card className='group glass-card border-0 shadow-none ring-0 relative flex w-full max-w-full flex-col gap-2 overflow-hidden rounded-none md:rounded-2xl py-0 transition-all duration-300'>
      {/* 图片预览 */}
      {images.length > 0 && mode !== 'hide' && (
        <div
          className='relative aspect-[16/9] w-full cursor-pointer overflow-hidden'
          onClick={onImgClick}
        >
          {!imageError && images.length > 0 ? (
            <>
              <LazyImage
                referrerPolicy={
                  images[0].includes('imgfor80') ? 'no-referrer' : 'origin'
                }
                src={images[0]}
                alt={article.title}
                className={`h-full w-full object-cover transition-all duration-500 group-hover:scale-110 ${
                  mode === 'blur' ? 'blur-md' : ''
                }`}
                onError={() => setImageError(true)}
              />

              {images.length > 1 && (
                <div className='absolute right-2 bottom-2 flex items-center gap-1 rounded-full bg-black/70 px-2 py-1 text-xs text-white backdrop-blur-sm'>
                  <ImageIcon className='h-3 w-3' />
                  {images.length}
                </div>
              )}

              <div className='absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 transition-opacity duration-300 group-hover:opacity-100'>
                <div className='rounded-full bg-white/20 p-3 backdrop-blur-sm'>
                  <ImageIcon className='h-6 w-6 text-white' />
                </div>
              </div>
            </>
          ) : (
            <div className='flex h-full w-full items-center justify-center bg-muted'>
              <ImageIcon className='h-12 w-12 text-muted-foreground/30' />
            </div>
          )}
        </div>
      )}

      {/* 内容区 */}
      <div className='relative min-w-0 flex-1 flex-col gap-3 py-2 px-4'>
        <div className='absolute top-2 right-2 z-10'>
          <DropdownMenu modal={false}>
            <DropdownMenuTrigger asChild>
              <Button
                size='icon'
                variant='ghost'
                className='h-8 w-8 rounded-full'
                onClick={(e) => e.stopPropagation()}
              >
                <MoreVertical className='h-4 w-4' />
              </Button>
            </DropdownMenuTrigger>

            <DropdownMenuContent
              align='end'
              className='w-40 bg-background/20 backdrop-blur-md'
            >
              {article.magnet?.length>0 && (
                <DropdownMenuItem onClick={handleCopyMagnet}>
                  <Copy className='mr-2 h-4 w-4' />
                  复制磁力
                </DropdownMenuItem>
              )}
              {article.edk?.length>0 && (
                <DropdownMenuItem onClick={handleCopyEd2k}>
                  <Copy className='mr-2 h-4 w-4' />
                  复制Ed2k
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={onDownload}>
                <Download className='mr-2 h-4 w-4' />
                推送下载
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className='flex flex-wrap items-center gap-2 pr-8 text-xs'>
          <Badge variant='default' className='shadow-sm'>
            {article.website}
          </Badge>
          <Badge variant='secondary' className='shadow-sm'>
            {article.section}
          </Badge>

          {article.category && (
            <Badge variant='outline' className='shadow-sm'>
              {article.category}
            </Badge>
          )}

          <span className='flex items-center gap-1 text-muted-foreground'>
            <CalendarIcon className='h-3 w-3' />
            {article.publish_date}
          </span>
        </div>
        <h6 className='mt-2 line-clamp-3 pr-2 text-sm leading-snug font-medium break-words transition-colors group-hover:text-primary first-line:indent-8'>
          {article.title}
        </h6>
        <div className='mt-2 flex flex-wrap items-center gap-2 text-xs'>
          {article.size > 0 && (
            <span className='flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 font-medium'>
              <Package className='h-3 w-3' />
              {article.size} MB
            </span>
          )}

          {article.in_stock && (
            <span className='flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-1 font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400'>
              <CheckCircle2 className='h-3 w-3' />
              已下载
            </span>
          )}

          {article.in_library && (
            <span className='flex items-center gap-1 rounded-full bg-sky-100 px-2.5 py-1 font-medium text-sky-700 dark:bg-sky-900/30 dark:text-sky-400'>
              <CheckCircle2 className='h-3 w-3' />
              已入库
            </span>
          )}
        </div>
      </div>
    </Card>
  )
}
