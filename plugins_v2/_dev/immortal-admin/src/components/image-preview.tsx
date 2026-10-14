// ImagePreview.tsx - 自动适配 PC / 移动端
import { useEffect, useRef, useState } from 'react'
import { X, ImageIcon, ChevronLeft, ChevronRight } from 'lucide-react'
import { TransformComponent, TransformWrapper } from 'react-zoom-pan-pinch'
import { useUIStore } from '@/stores/ui-store.ts'
import { cn } from '@/lib/utils.ts'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Button } from '@/components/ui/button.tsx'
import { Dialog, DialogContent } from '@/components/ui/dialog.tsx'

function PCPreview({
  images,
  alt,
  currentIndex,
  imageErrors,
  onPrev,
  onNext,
  onSelectIndex,
  onImageError,
  onClose,
  onPrevArticle,
  onNextArticle,
  hasPrevArticle,
  hasNextArticle,
}: PCPreviewProps) {
  const thumbsRef = useRef<HTMLDivElement>(null)

  // 键盘快捷键
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') onPrev()
      if (e.key === 'ArrowRight') onNext()
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onPrev, onNext, onClose])

  // 缩略图跟随滚动
  useEffect(() => {
    if (thumbsRef.current) {
      const thumb = thumbsRef.current.children[currentIndex] as HTMLElement
      thumb?.scrollIntoView({
        behavior: 'smooth',
        inline: 'center',
        block: 'nearest',
      })
    }
  }, [currentIndex])

  return (
    <div
      className={cn(
        'fixed inset-0 z-50 flex flex-col bg-background backdrop-blur-2xl'
      )}
    >
      {/* 顶栏 */}
      <div
        className={cn('flex items-center justify-between gap-3 border-b px-4 py-4 sm:px-8')}
      >
        <div className='flex min-w-0 items-center gap-2'>
          <span className='font-serif text-xs tracking-[0.18em]'>IMMORTAL</span>
          {(hasPrevArticle || hasNextArticle) && (
            <div className='flex items-center gap-2'>
              <Button
                type='button'
                size='sm'
                variant='outline'
                onClick={onPrevArticle}
                disabled={!hasPrevArticle}
                className='h-8 px-3'
              >
                上一篇
              </Button>
              <Button
                type='button'
                size='sm'
                variant='outline'
                onClick={onNextArticle}
                disabled={!hasNextArticle}
                className='h-8 px-3'
              >
                下一篇
              </Button>
            </div>
          )}
        </div>
        <span className='text-[13px] tracking-[0.1em]'>
          {String(currentIndex + 1).padStart(2, '0')} /{' '}
          {String(images.length).padStart(2, '0')}
        </span>
        <Button
          size='icon'
          variant='default'
          onClick={onClose}
          className='rounded-full border'
        >
          <X className='h-4 w-4' />
        </Button>
      </div>

      {alt && (
        <div className='border-b px-4 py-2 text-sm text-muted-foreground sm:px-8'>
          <p className='line-clamp-1'>{alt}</p>
        </div>
      )}

      {/* 主图区域 */}
      <div className='relative flex flex-1 items-center justify-center overflow-hidden'>
        {/* 左箭头 */}
        {images.length > 1 && (
          <Button
            variant='default'
            onClick={onPrev}
            className={cn(
              'absolute left-8 z-10 flex h-12 w-12 cursor-pointer items-center justify-center',
              'rounded-full border transition-all'
            )}
          >
            <ChevronLeft className='h-5 w-5' />
          </Button>
        )}

        {/* 图片 */}
        <div className='flex max-h-[65vh] max-w-[75vw] items-center justify-center'>
          {imageErrors.has(currentIndex) ? (
            <div
              className={cn(
                'flex h-[320px] w-[480px] flex-col items-center justify-center gap-4',
                'rounded-lg'
              )}
            >
              <ImageIcon className='h-16 w-16' />
              <p className='text-[13px]'>图片加载失败</p>
            </div>
          ) : (
            <TransformWrapper
              pinch={{ disabled: false }}
              doubleClick={{ disabled: false }}
            >
              <TransformComponent>
                <img
                  key={currentIndex}
                  src={images[currentIndex]}
                  alt={`${alt}-${currentIndex}`}
                  referrerPolicy={
                    images[currentIndex]?.includes('imgfor80')
                      ? 'no-referrer'
                      : 'origin'
                  }
                  className='max-h-[65vh] max-w-[75vw] rounded object-contain'
                  onError={() => onImageError(currentIndex)}
                  draggable={false}
                />
              </TransformComponent>
            </TransformWrapper>
          )}
        </div>

        {/* 右箭头 */}
        {images.length > 1 && (
          <Button
            variant='default'
            onClick={onNext}
            className={cn(
              'absolute right-8 z-10 flex h-12 w-12 cursor-pointer items-center justify-center',
              'rounded-full border transition-all',
              'hover:bg-white/[0.18]'
            )}
          >
            <ChevronRight className='h-5 w-5' />
          </Button>
        )}

        {/* 缩放提示 */}
        <span className='absolute top-4 right-6 text-[11px] tracking-[0.08em]'>
          滚轮 / 双击缩放
        </span>
      </div>

      {/* 缩略图条 */}
      {images.length > 1 && (
        <div className='border-t px-8 py-3.5'>
          <div
            ref={thumbsRef}
            className='scrollbar-hide flex justify-center gap-2 overflow-x-auto py-1'
          >
            {images.map((img, i) => (
              <button
                key={i}
                onClick={() => onSelectIndex(i)}
                className={cn(
                  'relative h-[50px] w-[72px] flex-shrink-0 cursor-pointer overflow-hidden rounded p-0 transition-all',
                  i === currentIndex
                    ? 'scale-[1.07] border-2 opacity-100'
                    : 'border-2 border-transparent opacity-40'
                )}
              >
                {imageErrors.has(i) ? (
                  <div className='flex h-full w-full items-center justify-center'>
                    <ImageIcon className='h-5 w-5' />
                  </div>
                ) : (
                  <img
                    src={img}
                    alt={`thumb-${i}`}
                    referrerPolicy={
                      img.includes('imgfor80') ? 'no-referrer' : 'origin'
                    }
                    className='h-full w-full object-cover'
                    onError={() => onImageError(i)}
                  />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── 移动端预览 ────────────────────────────────────────────
function MobilePreview({
  images,
  alt,
  currentIndex,
  imageErrors,
  onPrev,
  onNext,
  onSelectIndex,
  onImageError,
  onClose,
  onPrevArticle,
  onNextArticle,
  hasPrevArticle,
  hasNextArticle,
}: MobilePreviewProps) {
  const touchStart = useRef<{ x: number; y: number } | null>(null)
  const [sliding, setSliding] = useState<'left' | 'right' | null>(null)

  const handleTouchStart = (e: React.TouchEvent) => {
    touchStart.current = { x: e.touches[0].clientX, y: e.touches[0].clientY }
  }

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!touchStart.current) return
    const dx = e.changedTouches[0].clientX - touchStart.current.x
    const dy = e.changedTouches[0].clientY - touchStart.current.y
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
      const dir = dx < 0 ? 'left' : 'right'
      setSliding(dir)
      setTimeout(() => {
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        dir === 'left' ? onNext() : onPrev()
        setSliding(null)
      }, 180)
    }
    touchStart.current = null
  }

  return (
    <div className='fixed inset-0 z-50 flex flex-col bg-background pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]'>
      <div className='space-y-3 px-4 py-2'>
        <div className='flex items-center justify-between'>
          <Button
            onClick={onClose}
            className='cursor-pointer p-4'
            variant='outline'
          >
            <ChevronLeft className='h-8 w-8' />
          </Button>
          <span className='text-[14px]'>
            {currentIndex + 1} / {images.length}
          </span>
          <div className='w-9' />
        </div>
        {alt && <p className='line-clamp-2 text-sm text-muted-foreground'>{alt}</p>}
      </div>

      <div className='border-b' />

      {/* 主图 */}
      <div
        className='relative flex flex-1 items-center justify-center overflow-hidden'
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {imageErrors.has(currentIndex) ? (
          <div className='flex flex-col items-center justify-center gap-3'>
            <ImageIcon className='h-16 w-16' />
          </div>
        ) : (
          <TransformWrapper
            pinch={{ disabled: false }}
            doubleClick={{ disabled: false }}
            panning={{ disabled: true }}
          >
            <TransformComponent>
              <img
                key={currentIndex}
                src={images[currentIndex]}
                alt={`${alt}-${currentIndex}`}
                referrerPolicy={
                  images[currentIndex]?.includes('imgfor80')
                    ? 'no-referrer'
                    : 'origin'
                }
                className={cn(
                  'block max-h-full w-[100dvw] object-contain transition-all duration-200 ease-in-out select-none',
                  sliding ? 'opacity-0' : 'opacity-100',
                  sliding === 'left'
                    ? '-translate-x-6'
                    : sliding === 'right'
                      ? 'translate-x-6'
                      : 'translate-x-0'
                )}
                onError={() => onImageError(currentIndex)}
                draggable={false}
              />
            </TransformComponent>
          </TransformWrapper>
        )}

        {(hasPrevArticle || hasNextArticle) && (
          <div className='pointer-events-none absolute right-4 bottom-4 z-10'>
            <div className='pointer-events-auto ml-auto flex w-fit flex-col items-center gap-2'>
              <Button
                type='button'
                size='icon'
                variant='outline'
                className='h-12 w-12 rounded-full border bg-background/85 font-medium text-foreground shadow-md backdrop-blur'
                onClick={onPrevArticle}
                disabled={!hasPrevArticle}
                aria-label='上一篇'
              >
                上
              </Button>
              <Button
                type='button'
                size='icon'
                variant='default'
                className='h-14 w-14 rounded-full bg-primary/95 font-medium text-primary-foreground shadow-lg backdrop-blur'
                onClick={onNextArticle}
                disabled={!hasNextArticle}
                aria-label='下一篇'
              >
                下
              </Button>
            </div>
          </div>
        )}
      </div>

      <div className='space-y-3 pb-2'>

        {/* 点状指示器 */}
        {images.length > 1 && (
          <div className='flex items-center justify-center gap-2 py-1'>
            {images.map((_, i) => (
              <div
                key={i}
                onClick={() => onSelectIndex(i)}
                className={cn(
                  'h-[6px] cursor-pointer rounded-[3px] transition-all duration-200 ease-in-out',
                  i === currentIndex
                    ? 'w-[18px] bg-black dark:bg-white'
                    : 'w-[6px] bg-black/60 dark:bg-white/60'
                )}
              />
            ))}
          </div>
        )}

        {/* 缩略图条 */}
        {images.length > 1 && (
          <div className='scrollbar-hide flex gap-2 overflow-x-auto px-4'>
            {images.map((img, i) => (
              <div
                key={i}
                onClick={() => onSelectIndex(i)}
                className={cn(
                  'h-14 w-14 shrink-0 cursor-pointer overflow-hidden rounded-lg border-2 transition-all duration-200',
                  i === currentIndex
                    ? 'border-white opacity-100'
                    : 'border-transparent opacity-45'
                )}
              >
                {imageErrors.has(i) ? (
                  <div className='flex h-full w-full items-center justify-center'>
                    <ImageIcon className='h-4 w-4' />
                  </div>
                ) : (
                  <img
                    src={img}
                    alt={`thumb-${i}`}
                    referrerPolicy={
                      img.includes('imgfor80') ? 'no-referrer' : 'origin'
                    }
                    className='h-full w-full object-cover'
                    onError={() => onImageError(i)}
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface SharedPreviewProps {
  images: string[]
  alt: string
  currentIndex: number
  imageErrors: Set<number>
  onPrev: () => void
  onNext: () => void
  onSelectIndex: (i: number) => void
  onImageError: (i: number) => void
  onClose: () => void
  onPrevArticle?: () => void
  onNextArticle?: () => void
  hasPrevArticle?: boolean
  hasNextArticle?: boolean
}
type PCPreviewProps = SharedPreviewProps
type MobilePreviewProps = SharedPreviewProps

export function ImagePreview({
  images,
  alt,
  open,
  onClose,
  onPrevArticle,
  onNextArticle,
  hasPrevArticle = false,
  hasNextArticle = false,
}: {
  images: string[]
  alt: string
  open: boolean
  onClose: () => void
  onPrevArticle?: () => void
  onNextArticle?: () => void
  hasPrevArticle?: boolean
  hasNextArticle?: boolean
}) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [imageErrors, setImageErrors] = useState<Set<number>>(new Set())
  const isMobile = useIsMobile()
  const setHideBottomNav = useUIStore((s) => s.setHideBottomNav)
  const previewHistoryActiveRef = useRef(false)
  const closingFromPopStateRef = useRef(false)
  const onCloseRef = useRef(onClose)

  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    setHideBottomNav(open)
    return () => setHideBottomNav(false)
  }, [open, setHideBottomNav])

  useEffect(() => {
    if (open) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCurrentIndex(0)
      setImageErrors(new Set())
    }
  }, [open, images])

  useEffect(() => {
    if (!open || !isMobile) return

    closingFromPopStateRef.current = false
    previewHistoryActiveRef.current = true
    window.history.pushState({ __imagePreview: true }, '')

    const handlePopState = () => {
      if (!previewHistoryActiveRef.current) return
      previewHistoryActiveRef.current = false
      closingFromPopStateRef.current = true
      onCloseRef.current()
    }

    window.addEventListener('popstate', handlePopState)

    return () => {
      window.removeEventListener('popstate', handlePopState)
      if (previewHistoryActiveRef.current) {
        previewHistoryActiveRef.current = false
        if (!closingFromPopStateRef.current) {
          window.history.back()
        }
      }
      closingFromPopStateRef.current = false
    }
  }, [open, isMobile])

  if (!open) return null

  const sharedProps: SharedPreviewProps = {
    images,
    alt,
    currentIndex,
    imageErrors,
    onPrev: () => setCurrentIndex((i) => (i === 0 ? images.length - 1 : i - 1)),
    onNext: () => setCurrentIndex((i) => (i === images.length - 1 ? 0 : i + 1)),
    onSelectIndex: (i) => setCurrentIndex(i),
    onImageError: (i) => setImageErrors((prev) => new Set(prev).add(i)),
    onClose,
    onPrevArticle,
    onNextArticle,
    hasPrevArticle,
    hasNextArticle,
  }

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent fullScreen className='gap-0'>
        {isMobile ? (
          <MobilePreview {...sharedProps} />
        ) : (
          <PCPreview {...sharedProps} />
        )}
      </DialogContent>
    </Dialog>
  )
}
