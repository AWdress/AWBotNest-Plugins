import { useEffect } from 'react'
import * as z from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { RotateCcw, Save } from 'lucide-react'
import { toast } from 'sonner'
import {
  DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG,
  getSubscribePreferenceConfig,
  saveSubscribePreferenceConfig,
  SUBSCRIBE_PREFERENCE_CONFIG_QUERY_KEY,
  type SubscribePreferenceConfig,
} from '@/api/subscribe-preference.ts'
import { Button } from '@/components/ui/button.tsx'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Switch } from '@/components/ui/switch.tsx'
import { Textarea } from '@/components/ui/textarea.tsx'

const positiveIntegerMessage = '请输入大于等于 1 的整数'
const nonNegativeIntegerMessage = '请输入大于等于 0 的整数'

const formSchema = z.object({
  earliest_release_date: z.string(),
  exclude_vr: z.boolean(),
  max_coactors: z.string().refine((value) => {
    if (!value.trim()) return true
    const parsed = Number(value)
    return Number.isInteger(parsed) && parsed >= 0
  }, nonNegativeIntegerMessage),
  max_page: z.string().refine((value) => {
    if (!value.trim()) return true
    const parsed = Number(value)
    return Number.isInteger(parsed) && parsed >= 1
  }, positiveIntegerMessage),
  replace_max_page: z.string().refine((value) => {
    if (!value.trim()) return true
    const parsed = Number(value)
    return Number.isInteger(parsed) && parsed >= 1
  }, positiveIntegerMessage),
  is_single: z.boolean(),
  number_prefix_blacklist_text: z.string(),
  keyword_blacklist_text: z.string(),
})

type FormValues = z.infer<typeof formSchema>

const defaultValues: FormValues = {
  earliest_release_date: '',
  exclude_vr: false,
  max_coactors: '',
  max_page: '',
  replace_max_page: '',
  is_single: false,
  number_prefix_blacklist_text: '',
  keyword_blacklist_text: '',
}

function toFormValues(config?: SubscribePreferenceConfig | null): FormValues {
  const payload = config || DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG
  return {
    earliest_release_date: payload.earliest_release_date || '',
    exclude_vr: Boolean(payload.exclude_vr),
    max_coactors:
      payload.max_coactors == null ? '' : String(payload.max_coactors),
    max_page: payload.max_page == null ? '' : String(payload.max_page),
    replace_max_page:
      payload.replace_max_page == null ? '' : String(payload.replace_max_page),
    is_single: Boolean(payload.is_single),
    number_prefix_blacklist_text: (payload.number_prefix_blacklist || []).join(
      '\n'
    ),
    keyword_blacklist_text: (payload.keyword_blacklist || []).join('\n'),
  }
}

function toPayload(values: FormValues): SubscribePreferenceConfig {
  const parseInteger = (value: string) => {
    const trimmed = value.trim()
    return trimmed ? Number(trimmed) : null
  }
  const splitTextList = (value: string) =>
    value
      .split(/[\n,，;；、\s]+/g)
      .map((item) => item.trim())
      .filter(Boolean)
  const parsePrefixList = (value: string) => {
    const tokens = splitTextList(value).map((item) => item.toUpperCase())
    return Array.from(new Set(tokens))
  }
  const parseKeywordList = (value: string) => {
    const tokens = splitTextList(value)
    const deduped: string[] = []
    const seen = new Set<string>()
    for (const token of tokens) {
      const key = token.toLowerCase()
      if (seen.has(key)) continue
      seen.add(key)
      deduped.push(token)
    }
    return deduped
  }

  return {
    earliest_release_date: values.earliest_release_date.trim() || null,
    exclude_vr: values.exclude_vr,
    max_coactors: parseInteger(values.max_coactors),
    max_page: parseInteger(values.max_page),
    replace_max_page: parseInteger(values.replace_max_page),
    is_single: values.is_single,
    number_prefix_blacklist: parsePrefixList(values.number_prefix_blacklist_text),
    keyword_blacklist: parseKeywordList(values.keyword_blacklist_text),
  }
}

export function PreferenceManager() {
  const queryClient = useQueryClient()
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
  })

  const { data, isLoading } = useQuery({
    queryKey: SUBSCRIBE_PREFERENCE_CONFIG_QUERY_KEY,
    queryFn: async () => {
      const res = await getSubscribePreferenceConfig()
      return res.data || DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG
    },
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    form.reset(toFormValues(data))
  }, [data, form])

  const handleSubmit = async (values: FormValues) => {
    const payload = toPayload(values)
    const res = await saveSubscribePreferenceConfig(payload)
    await queryClient.invalidateQueries({
      queryKey: SUBSCRIBE_PREFERENCE_CONFIG_QUERY_KEY,
      exact: true,
    })
    toast.success(res.message || '订阅喜好已保存')
  }

  const handleReset = () => {
    form.reset(defaultValues)
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(handleSubmit)}
        className='max-w-2xl space-y-5'
      >
        <div className='grid gap-4 md:grid-cols-2'>
          <FormField
            control={form.control}
            name='earliest_release_date'
            render={({ field }) => (
              <FormItem>
                <FormLabel>最早发行日期</FormLabel>
                <FormControl>
                  <Input type='date' {...field} />
                </FormControl>
                <FormDescription>
                  bot 创建演员订阅或综合订阅时，未显式指定则使用此默认值。
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name='max_coactors'
            render={({ field }) => (
              <FormItem>
                <FormLabel>最大共演人数</FormLabel>
                <FormControl>
                  <Input
                    inputMode='numeric'
                    placeholder='留空表示不限'
                    {...field}
                  />
                </FormControl>
                <FormDescription>同时用于演员订阅和综合订阅。</FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name='max_page'
            render={({ field }) => (
              <FormItem>
                <FormLabel>最大页数</FormLabel>
                <FormControl>
                  <Input
                    inputMode='numeric'
                    placeholder='留空表示不限'
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  仅用于 bot 创建演员订阅时的默认抓取页数。
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name='replace_max_page'
            render={({ field }) => (
              <FormItem>
                <FormLabel>替换最大页数</FormLabel>
                <FormControl>
                  <Input
                    inputMode='numeric'
                    placeholder='留空表示不替换'
                    {...field}
                  />
                </FormControl>
                <FormDescription>
                  仅用于 bot 创建演员订阅时覆盖默认抓取页数(建议1)。
                </FormDescription>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <FormField
          control={form.control}
          name='number_prefix_blacklist_text'
          render={({ field }) => (
            <FormItem>
              <FormLabel>番号前缀黑名单</FormLabel>
              <FormControl>
                <Textarea
                  placeholder={
                    '每行或用逗号分隔一个前缀，例如：\nFC2\nSSNI\nABP'
                  }
                  className='min-h-28'
                  {...field}
                />
              </FormControl>
              <FormDescription>
                保存后会自动按换行、空格、逗号、顿号分割，统一用于演员订阅、综合订阅和榜单订阅的番号过滤。
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name='keyword_blacklist_text'
          render={({ field }) => (
            <FormItem>
              <FormLabel>关键字黑名单</FormLabel>
              <FormControl>
                <Textarea
                  placeholder={
                    '每行或用逗号分隔一个关键字，例如：\n合集\n重口\nAI'
                  }
                  className='min-h-28'
                  {...field}
                />
              </FormControl>
              <FormDescription>
                保存后会自动按换行、空格、逗号、顿号分割；影片任一关键字段包含任一关键字时，将在演员订阅、综合订阅和榜单订阅中跳过。
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <div className='grid gap-4 md:grid-cols-2'>
          <FormField
            control={form.control}
            name='exclude_vr'
            render={({ field }) => (
              <FormItem className='flex items-center justify-between rounded-xl border px-4 py-3'>
                <div className='space-y-1'>
                  <FormLabel>排除 VR</FormLabel>
                  <FormDescription>
                    bot 创建订阅时，默认过滤 VR 影片。
                  </FormDescription>
                </div>
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name='is_single'
            render={({ field }) => (
              <FormItem className='flex items-center justify-between rounded-xl border px-4 py-3'>
                <div className='space-y-1'>
                  <FormLabel>仅单体</FormLabel>
                  <FormDescription>
                    仅用于 bot 创建演员订阅时默认只抓取单体作品。
                  </FormDescription>
                </div>
                <FormControl>
                  <Switch
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
              </FormItem>
            )}
          />
        </div>

        <div className='flex flex-wrap gap-2'>
          <Button type='submit' disabled={isLoading}>
            <Save className='mr-2 h-4 w-4' />
            保存喜好配置
          </Button>
          <Button type='button' variant='outline' onClick={handleReset}>
            <RotateCcw className='mr-2 h-4 w-4' />
            重置表单
          </Button>
        </div>
      </form>
    </Form>
  )
}
