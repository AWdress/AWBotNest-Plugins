import { useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import {
  Download,
  LayoutGrid,
  Library,
  List,
  Loader2,
  Upload,
} from 'lucide-react'
import { toast } from 'sonner'
import { downloadData, uploadArticle } from '@/api/article.ts'
import { useIsMobile } from '@/hooks/use-mobile.tsx'
import { Button } from '@/components/ui/button.tsx'
import { ConfigDrawer } from '@/components/config-drawer'
import { ContentTitle } from '@/components/content-title.tsx'
import { ImageModeSwitch } from '@/components/image-mode-switch.tsx'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { Search } from '@/components/search'
import { ServerLogDialog } from '@/components/server-log-dialog.tsx'
import { ThemeSwitch } from '@/components/theme-switch'
import { useUIStore } from '@/stores/ui-store'
import { ArticlesDesktop } from '@/features/articles/components/articles-desktop.tsx'
import { ArticlesMobile } from '@/features/articles/components/articles-mobile.tsx'
import { ArticlesTable } from '@/features/articles/components/articles-table.tsx'

export function Articles() {
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()
  const [view, setView] = useState<'grid' | 'list'>('grid')
  const [importing, setImporting] = useState(false)
  const [exporting, setExporting] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const routeNamingMode = useUIStore((s) => s.routeNamingMode)
  const isSimple = routeNamingMode === 'simple'

  const handleExport = async () => {
    try {
      setExporting(true)
      await downloadData()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '导出失败，请重试。')
    } finally {
      setExporting(false)
    }
  }
  const handleImport = async (file: File) => {
    try {
      setImporting(true)
      const res = await uploadArticle(file)
      if (res.code === 0) {
        toast.success(res.message)
        await queryClient.invalidateQueries()
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '导入失败，请检查文件后重试。')
    } finally {
      setImporting(false)
    }
  }
  return (
    <>
      <Header fixed>
        <Search />
        <div className='ms-auto flex items-center space-x-4'>
          <ServerLogDialog />
          <Button
            variant='ghost'
            size='icon'
            aria-label='导入文章数据'
            onClick={() => fileRef.current?.click()}
            disabled={importing}
          >
            {importing ? (
              <Loader2 size={18} className='animate-spin' />
            ) : (
              <Upload size={18} />
            )}
          </Button>
          <Button
            variant='ghost'
            size='icon'
            aria-label='导出文章数据'
            onClick={() => handleExport()}
            disabled={exporting}
          >
            {exporting ? (
              <Loader2 size={18} className='animate-spin' />
            ) : (
              <Download size={18} />
            )}
          </Button>
          <input
            ref={fileRef}
            type='file'
            hidden
            accept='.xls,.xlsx,.csv'
            onChange={(e) => {
              const selectedFile = e.currentTarget.files?.[0]
              e.currentTarget.value = ''
              if (selectedFile) {
                handleImport(selectedFile)
              }
            }}
          />
          {!isMobile && (
            <Button
              variant='ghost'
              size='icon'
              onClick={() => setView(view === 'grid' ? 'list' : 'grid')}
              title={view === 'grid' ? '切换为列表' : '切换为网格'}
            >
              {view === 'grid' ? <List size={18} /> : <LayoutGrid size={18} />}
            </Button>
          )}
          <ImageModeSwitch />
          <ThemeSwitch />
          <ConfigDrawer />
        </div>
      </Header>

      <Main fixed>
        <ContentTitle
          title={isSimple ? '文章管理' : '藏经阁'}
          description={
            isSimple
              ? '管理文章数据，支持导入、导出和搜索。'
              : '收录诸篇卷册，可检索、导入、导出与翻阅。'
          }
          icon={<Library className='h-8 w-8 text-primary' />}
        />

        {isMobile ? (
          <ArticlesMobile />
        ) : view === 'grid' ? (
          <ArticlesDesktop />
        ) : (
          <ArticlesTable />
        )}
      </Main>
    </>
  )
}
