import {
  type ImgHTMLAttributes,
  useEffect,
  useRef,
  useState,
} from 'react'

type LazyImageProps = ImgHTMLAttributes<HTMLImageElement> & {
  rootMargin?: string
}

export function LazyImage({
  src,
  loading = 'lazy',
  decoding = 'async',
  rootMargin = '200px',
  ...props
}: LazyImageProps) {
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [shouldLoad, setShouldLoad] = useState(loading === 'eager')

  useEffect(() => {
    if (!src) {
      setShouldLoad(false)
      return
    }

    if (loading === 'eager') {
      setShouldLoad(true)
      return
    }

    const node = imgRef.current
    if (!node) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return
        setShouldLoad(true)
        observer.disconnect()
      },
      { rootMargin }
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [loading, rootMargin, src])

  return (
    <img
      ref={imgRef}
      src={shouldLoad ? src : undefined}
      loading={loading}
      decoding={decoding}
      {...props}
    />
  )
}
