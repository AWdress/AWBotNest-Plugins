import { useEffect } from 'react'
import { z } from 'zod'
import { useForm, useWatch } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, FolderOpen, HardDrive, Check } from 'lucide-react'
import { toast } from 'sonner'
import {
  type ArticleListResult,
  batchDownloadArticle,
  batchManulDownloadArticle,
} from '@/api/article'
import { fetchDownloaderList } from '@/api/config'
import { getCookie, setCookie } from '@/lib/cookies.ts'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
} from '@/components/ui/dialog.tsx'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { ScrollArea } from '@/components/ui/scroll-area'

const formSchema = z.object({
  downloader: z.string().min(1, '请选择下载器'),
  savePath: z.string().min(1, '请选择下载目录'),
})

type FormValues = z.infer<typeof formSchema>

interface DownloaderDialogProps {
  articleIdList: number[]
  open: boolean
  onOpenChange: (open: boolean) => void
}

const DOWNLOAD_PREF_KEY = 'download:last-selection'

export function DownloaderDialog({
  open,
  onOpenChange,
  articleIdList,
}: DownloaderDialogProps) {
  const queryClient = useQueryClient()

  const { data: downloaders, isLoading } = useQuery({
    queryKey: ['downloaders'],
    queryFn: async () => {
      const res = await fetchDownloaderList()
      return res.data
    },
    staleTime: 5 * 60 * 1000,
    enabled: open,
  })

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      downloader: 'auto',
      savePath: 'auto',
    },
  })

  const selectedDownloader = useWatch({
    control: form.control,
    name: 'downloader',
  })

  const currentDownloader = downloaders?.find(
    (d) => d.id === selectedDownloader
  )

  const updateSockStatus = () => {
    queryClient.setQueriesData(
      { queryKey: ['articles'], exact: false },
      (oldData: ArticleListResult) => {
        if (!oldData) return oldData
        return {
          ...oldData,
          items: oldData.items.map((item) =>
            articleIdList.includes(item.id) ? { ...item, in_stock: true } : item
          ),
        }
      }
    )
  }

  const submitMutation = useMutation({
    mutationFn: async (values: FormValues) => {
      if (selectedDownloader === 'auto') {
        return await batchDownloadArticle(articleIdList.join(','))
      } else {
        return await batchManulDownloadArticle(
          articleIdList.join(','),
          values.downloader,
          values.savePath
        )
      }
    },
    onSuccess: (res) => {
      if (res.code === 0) {
        toast.success(res.message)
        onOpenChange(false)
        updateSockStatus()
        setCookie(
          DOWNLOAD_PREF_KEY,
          JSON.stringify({
            downloader: selectedDownloader,
            savePath: form.getValues('savePath'),
          })
        )
      }
    },
    onError: (err: Error) => {
      toast.error(`推送失败，请重试:${err}`)
    },
  })

  useEffect(() => {
    if (!open) return

    const raw = getCookie(DOWNLOAD_PREF_KEY)
    if (!raw) return

    try {
      const { downloader, savePath } = JSON.parse(raw)

      form.reset({
        downloader: downloader ?? 'auto',
        savePath: savePath ?? 'auto',
      })
    } catch {
      // ignore malformed storage
    }
  }, [form, open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
      <DialogContent onOpenAutoFocus={(e) => e.preventDefault()} className='bg-background/40 backdrop-blur-lg'>
        <DialogHeader>
          <DialogTitle>选择下载器</DialogTitle>
        </DialogHeader>
        {isLoading ? (
          <div className='flex h-48 items-center justify-center'>
            <div className='flex flex-col items-center gap-2 text-muted-foreground'>
              <div className='h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent' />
              <p className='text-sm'>加载配置中...</p>
            </div>
          </div>
        ) : downloaders?.length === 0 ? (
          <div className='flex h-48 flex-col items-center justify-center gap-2 text-muted-foreground'>
            <HardDrive className='h-12 w-12 opacity-30' />
            <p className='text-sm'>未配置任何下载器</p>
            <p className='text-xs'>请先在设置中配置下载器</p>
          </div>
        ) : (
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit((values) =>
                submitMutation.mutate(values)
              )}
              className='space-y-6 py-4'
            >
              {/* 下载器选择 */}
              <FormField
                control={form.control}
                name='downloader'
                render={({ field }) => (
                  <FormItem className='space-y-2'>
                    <FormLabel className='flex items-center gap-2'>
                      <HardDrive className='h-4 w-4' />
                      下载器
                    </FormLabel>
                    <FormControl>
                      <RadioGroup
                        onValueChange={(value) => {
                          field.onChange(value)
                          // 当选择下载器时，自动设置路径
                          if (value === 'auto') {
                            form.setValue('savePath', 'auto')
                          } else {
                            const downloader = downloaders?.find(
                              (d) => d.id === value
                            )
                            if (
                              downloader &&
                              downloader.save_paths.length > 0
                            ) {
                              form.setValue(
                                'savePath',
                                downloader.save_paths[0].path
                              )
                            }
                          }
                        }}
                        value={field.value}
                        className='space-y-2'
                      >
                        {/* 自动选择选项 */}
                        <div
                          className={`flex items-center space-x-3 rounded-lg border p-3 backdrop-blur-sm transition-all ${
                            field.value === 'auto'
                              ? 'border-primary bg-primary/10'
                              : 'border-border/50 bg-background/30 hover:border-primary/50 hover:bg-background/40'
                          }`}
                        >
                          <RadioGroupItem value='auto' id='auto' />
                          <Label
                            htmlFor='auto'
                            className='flex flex-1 cursor-pointer items-center justify-between'
                          >
                            <div className='flex flex-col gap-1'>
                              <span className='font-medium'>
                                🎯 自动选择（推荐）
                              </span>
                              <span className='text-xs text-muted-foreground'>
                                由服务端自动判断最佳下载器和目录
                              </span>
                            </div>
                            {field.value === 'auto' && (
                              <Check className='h-4 w-4 flex-shrink-0 text-primary' />
                            )}
                          </Label>
                        </div>

                        {downloaders?.map((downloader) => (
                          <div
                            key={downloader.id}
                            className={`flex items-center space-x-3 rounded-lg border p-3 backdrop-blur-sm transition-all ${
                              field.value === downloader.id
                                ? 'border-primary bg-primary/10'
                                : 'border-border/50 bg-background/30 hover:border-primary/50 hover:bg-background/40'
                            }`}
                          >
                            <RadioGroupItem
                              value={downloader.id}
                              id={downloader.id}
                            />
                            <Label
                              htmlFor={downloader.id}
                              className='flex flex-1 cursor-pointer items-center justify-between'
                            >
                              <span className='font-medium'>
                                {downloader.id}
                              </span>
                              {field.value === downloader.id && (
                                <Check className='h-4 w-4 text-primary' />
                              )}
                            </Label>
                          </div>
                        ))}
                      </RadioGroup>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {selectedDownloader !== 'auto' && currentDownloader && (
                <>
                  <FormField
                    control={form.control}
                    name='savePath'
                    render={({ field }) => (
                      <FormItem className='space-y-2'>
                        <FormLabel className='flex items-center gap-2'>
                          <FolderOpen className='h-4 w-4' />
                          下载目录
                          <span className='text-xs font-normal text-muted-foreground'>
                            ({currentDownloader.save_paths.length} 个可用目录)
                          </span>
                        </FormLabel>
                        <FormControl>
                          <ScrollArea className='h-[160px] rounded-md border border-border/50 bg-background/30 backdrop-blur-sm'>
                            <RadioGroup
                              onValueChange={field.onChange}
                              value={field.value}
                              className='p-2'
                            >
                              {currentDownloader.save_paths.map(
                                (pathObj, index) => (
                                  <div
                                    key={index}
                                    className={`flex items-start space-x-3 rounded-md p-2 backdrop-blur-sm transition-all ${
                                      field.value === pathObj.path
                                        ? 'bg-primary/15'
                                        : 'hover:bg-muted/30'
                                    }`}
                                  >
                                    <RadioGroupItem
                                      value={pathObj.path}
                                      id={`path-${index}`}
                                      className='mt-0.5'
                                    />
                                    <Label
                                      htmlFor={`path-${index}`}
                                      className='flex flex-1 cursor-pointer flex-col gap-1'
                                    >
                                      <div className='flex items-center justify-between gap-2'>
                                        <span className='font-mono text-sm break-all'>
                                          {currentDownloader.id === 'thunder'
                                            ? pathObj.label
                                            : pathObj.path}
                                        </span>
                                        {field.value === pathObj.path && (
                                          <Check className='h-4 w-4 flex-shrink-0 text-primary' />
                                        )}
                                      </div>
                                    </Label>
                                  </div>
                                )
                              )}
                            </RadioGroup>
                          </ScrollArea>
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </>
              )}

              {/* 提交按钮 */}
              <div className='flex justify-end gap-2'>
                <Button
                  type='submit'
                  disabled={submitMutation.isPending}
                  className='w-full'
                >
                  {submitMutation.isPending ? (
                    <>
                      <div className='mr-2 h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent' />
                      推送中...
                    </>
                  ) : (
                    <>
                      <Download className='mr-2 h-4 w-4' />
                      确认推送
                    </>
                  )}
                </Button>
              </div>
            </form>
          </Form>
        )}
      </DialogContent>
    </Dialog>
  )
}
