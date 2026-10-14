import { useEffect } from 'react'
import * as z from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Save, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { deleteConfig, getConfig, postConfig } from '@/api/config.ts'
import { Button } from '@/components/ui/button.tsx'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { Input } from '@/components/ui/input.tsx'
import { ConfirmButton } from '@/components/confirm-button.tsx'
import { PathListInput } from '@/features/settings/downloader/path-input-list.tsx'

const cloudNasSchema = z.object({
  url: z.string().min(1, '输入地址'),
  token: z.string().min(1, '输入API令牌'),
  save_paths: z.array(
    z.object({
      path: z.string().min(1, '输入保存地址'),
      label: z.string().min(1, '输入保存地址别名'),
    })
  ),
})

type downloadValues = z.infer<typeof cloudNasSchema>
const defaultValues= {
  url: '',
  token: '',
  save_paths: [],
}

export function CloudNas({ downloaderId }: { downloaderId: string }) {
  const downloader = useForm<downloadValues>({
    resolver: zodResolver(cloudNasSchema),
    defaultValues,
  })
  const queryClient = useQueryClient()

  const { data } = useQuery({
    queryKey: ['downloader', downloaderId],
    queryFn: async () => {
      const res = await getConfig<downloadValues>('Downloader.' + downloaderId)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const updateMutation = useMutation({
    mutationFn: async (values: downloadValues) => {
      return await postConfig('Downloader.' + downloaderId, values as never)
    },
    onSuccess: (res) => {
      toast.success(res.message)
      queryClient.invalidateQueries({ queryKey: ['downloader', downloaderId] })
      queryClient.invalidateQueries({ queryKey: ['downloaders'] })
    },
  })

  const handleDeleteConfig = async () => {
    const res = await deleteConfig('Downloader.' + downloaderId)
    if (res.code === 0) {
      toast.success(res.message)
      queryClient.invalidateQueries({ queryKey: ['downloader', downloaderId] })
      queryClient.invalidateQueries({ queryKey: ['downloaders'] })
      downloader.reset(defaultValues)
    }
  }

  useEffect(() => {
    if (data) {
      downloader.reset(data)
    }
  }, [data, downloader])

  return (
    <Form {...downloader}>
      <form
        onSubmit={downloader.handleSubmit((values) =>
          updateMutation.mutate(values)
        )}
        className='max-w-md space-y-4'
      >
        <FormField
          control={downloader.control}
          name='url'
          render={({ field }) => (
            <FormItem>
              <FormLabel>WEB UI地址</FormLabel>
              <FormControl>
                <Input placeholder='输入WEB UI地址' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={downloader.control}
          name='token'
          render={({ field }) => (
            <FormItem>
              <FormLabel>令牌</FormLabel>
              <FormControl>
                <Input placeholder='输入CloudNas 令牌' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={downloader.control}
          name='save_paths'
          render={({ field }) => (
            <FormItem>
              <FormLabel>保存目录</FormLabel>
              <FormControl>
                <PathListInput value={field.value} onChange={field.onChange} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className='flex gap-2'>
          <Button type='submit'>
            <Save />
            保存配置
          </Button>
          <ConfirmButton
            title="确认删除该配置"
            variant='destructive'
            triggerText={<Trash2 className='h-4 w-4' />}
            onConfirm={handleDeleteConfig}
          />
        </div>
      </form>
    </Form>
  )
}
