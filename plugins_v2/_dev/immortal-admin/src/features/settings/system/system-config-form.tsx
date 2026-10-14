import { useEffect } from 'react'
import * as z from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { toast } from 'sonner'
import { getConfig, postConfig } from '@/api/config.ts'
import { Button } from '@/components/ui/button.tsx'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { Input } from '@/components/ui/input'

const formScheme = z.object({
  FLARE_SOLVERR_URL: z.string(),
  PROXY: z.string(),
  JAVDB_API_HOST: z.string(),
})

type formValues = z.infer<typeof formScheme>
const CONFIG_KEY = 'SystemConfig'
const CONFIG_QUERY_KEY = [CONFIG_KEY] as const

export function SystemConfigForm() {
  const queryClient = useQueryClient()
  const form = useForm<formValues>({
    resolver: zodResolver(formScheme),
    defaultValues: {
      FLARE_SOLVERR_URL: '',
      PROXY: '',
      JAVDB_API_HOST: '',
    },
  })

  const handleSubmit = async (data: formValues) => {
    const res = await postConfig(CONFIG_KEY, data as never)
    await queryClient.invalidateQueries({ queryKey: CONFIG_QUERY_KEY, exact: true })
    toast.success(res.message)
  }

  const { data } = useQuery({
    queryKey: CONFIG_QUERY_KEY,
    queryFn: async () => {
      const res = await getConfig<formValues>(CONFIG_KEY)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (data) {
      form.reset({ FLARE_SOLVERR_URL: data.FLARE_SOLVERR_URL ?? '', PROXY: data.PROXY ?? '', JAVDB_API_HOST: data.JAVDB_API_HOST ?? '' })
    }
  }, [data, form])

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleSubmit)}
        className='max-w-md space-y-4'
      >
        <FormField
          control={form.control}
          name='FLARE_SOLVERR_URL'
          render={({ field }) => (
            <FormItem>
              <FormLabel>FlareSolverr</FormLabel>
              <FormControl>
                <Input placeholder='输入 FlareSolverr 地址' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name='PROXY'
          render={({ field }) => (
            <FormItem>
              <FormLabel>代理地址</FormLabel>
              <FormControl>
                <Input placeholder='输入代理地址' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name='JAVDB_API_HOST'
          render={({ field }) => (
            <FormItem>
              <FormLabel>JAVDB 接口地址</FormLabel>
              <FormControl>
                <Input placeholder='输入 JAVDB 接口地址' {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type='submit'>
          <Save />
          保存配置
        </Button>
      </form>
    </Form>
  )
}
