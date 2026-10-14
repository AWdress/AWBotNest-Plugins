import { type WheelEvent, useEffect, useMemo, useRef, useState } from 'react'
import * as z from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronsUpDown, Regex, Scale } from 'lucide-react'
import { toast } from 'sonner'
import {
  flattenSectionsByWebsite,
  getCategories,
  type Section,
  type WebsiteCategoryTree,
} from '@/api/article.ts'
import { fetchDownloaderList } from '@/api/config.ts'
import {
  addRule,
  deleteRule,
  getRules,
  type Rule,
  updateRule,
} from '@/api/rule.ts'
import { Badge } from '@/components/ui/badge.tsx'
import { Button } from '@/components/ui/button.tsx'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogOverlay,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog.tsx'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form.tsx'
import { Input } from '@/components/ui/input.tsx'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select.tsx'
import { RuleTableDesktop } from '@/features/settings/rule/rule-table-desktop.tsx'
import { RuleTableMobile } from '@/features/settings/rule/rule-table-mobile.tsx'
import { useIsMobile } from '@/hooks/use-mobile.tsx'

const ALL_VALUE = 'ALL'

const formSchema = z.object({
  id: z.number(),
  website: z.array(z.string()).min(1, '至少选择一个站点'),
  section: z.array(z.string()).min(1, '至少选择一个板块'),
  category: z.array(z.string()).min(1, '至少选择一个分类'),
  regex: z.string(),
  downloader: z.string().min(1, '请选择下载器'),
  save_path: z.string().min(1, '请选择保存路径'),
})

type FormValues = z.infer<typeof formSchema>

type RuleOption = {
  value: string
  label: string
  count?: number
}

const defaultValues: FormValues = {
  id: 0,
  website: [ALL_VALUE],
  section: [ALL_VALUE],
  category: [ALL_VALUE],
  regex: '',
  downloader: '',
  save_path: '',
}

function normalizeSelection(values: string[], nextValue: string): string[] {
  if (nextValue === ALL_VALUE) {
    return [ALL_VALUE]
  }

  const current = values.filter((item) => item !== ALL_VALUE)
  if (current.includes(nextValue)) {
    const filtered = current.filter((item) => item !== nextValue)
    return filtered.length > 0 ? filtered : [ALL_VALUE]
  }
  return [...current, nextValue]
}

function MultiSelectField({
  label,
  value,
  options,
  onChange,
  placeholder,
  emptyText,
}: {
  label: string
  value: string[]
  options: RuleOption[]
  onChange: (value: string[]) => void
  placeholder: string
  emptyText: string
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const containerRef = useRef<HTMLDivElement | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const selectedLabels = useMemo(() => {
    if (value.includes(ALL_VALUE)) {
      return ['不限']
    }
    const optionMap = new Map(options.map((item) => [item.value, item.label]))
    return value.map((item) => optionMap.get(item) ?? item)
  }, [options, value])

  const filteredOptions = useMemo(() => {
    const keyword = query.trim().toLocaleLowerCase()
    const allOptions = [{ value: ALL_VALUE, label: '不限' }, ...options]
    if (!keyword) {
      return allOptions
    }
    return allOptions.filter((option) => {
      const label = option.label.toLocaleLowerCase()
      const value = option.value.toLocaleLowerCase()
      return label.includes(keyword) || value.includes(keyword)
    })
  }, [options, query])

  useEffect(() => {
    if (!open) {
      return
    }

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    window.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('touchstart', handlePointerDown)
    return () => {
      window.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('touchstart', handlePointerDown)
    }
  }, [open])

  const handleListWheel = (event: WheelEvent<HTMLDivElement>) => {
    const element = event.currentTarget
    if (element.scrollHeight <= element.clientHeight) {
      return
    }
    event.stopPropagation()
  }

  const panel = (
    <div className='rounded-md border bg-popover text-popover-foreground shadow-md'>
      <div className='border-b p-2'>
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={placeholder}
          className='h-9'
        />
      </div>
      <div
        ref={listRef}
        onWheel={handleListWheel}
        className='max-h-[min(60vh,18rem)] overflow-y-auto overscroll-contain p-1'
      >
        {filteredOptions.length === 0 ? (
          <div className='py-6 text-center text-sm text-muted-foreground'>
            {emptyText}
          </div>
        ) : (
          filteredOptions.map((option) => {
            const checked = value.includes(option.value)
            const toggleOption = () => onChange(normalizeSelection(value, option.value))
            return (
              <button
                key={option.value}
                type='button'
                onClick={toggleOption}
                className='hover:bg-accent hover:text-accent-foreground flex w-full min-w-0 items-center gap-2 overflow-hidden rounded-sm px-2 py-1.5 text-left text-sm'
              >
                <Check
                  className={`h-4 w-4 shrink-0 ${checked ? 'opacity-100' : 'opacity-0'}`}
                />
                <span className='min-w-0 flex-1 truncate'>{option.label}</span>
                {option.count ? (
                  <span className='shrink-0 text-xs text-muted-foreground'>
                    {option.count}
                  </span>
                ) : null}
              </button>
            )
          })
        )}
      </div>
    </div>
  )

  return (
    <FormItem>
      <FormLabel>{label}</FormLabel>
      <div ref={containerRef} className='space-y-2'>
        <FormControl>
          <Button
            type='button'
            variant='outline'
            role='combobox'
            onClick={() => setOpen((prev) => !prev)}
            className='h-auto min-h-10 w-full justify-between gap-2 px-3 py-2'
          >
            <div className='flex min-w-0 flex-wrap gap-1'>
              {selectedLabels.length > 0 ? (
                selectedLabels.map((item) => (
                  <Badge key={item} variant='secondary' className='max-w-full truncate'>
                    {item}
                  </Badge>
                ))
              ) : (
                <span className='text-muted-foreground'>{placeholder}</span>
              )}
            </div>
            <ChevronsUpDown className='size-4 shrink-0 opacity-60' />
          </Button>
        </FormControl>
        {open ? panel : null}
      </div>
      <FormMessage />
    </FormItem>
  )
}

function buildCategoryOptions(
  sections: Section[] | undefined,
  selectedSections: string[]
) {
  if (!sections) {
    return []
  }

  const allowAllSections = selectedSections.includes(ALL_VALUE)
  const counters = new Map<string, number>()

  sections.forEach((section) => {
    if (!allowAllSections && !selectedSections.includes(section.name)) {
      return
    }
    section.categories?.forEach((category) => {
      counters.set(
        category.name,
        (counters.get(category.name) ?? 0) + category.count
      )
    })
  })

  return [...counters.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([name, count]) => ({ value: name, label: name, count }))
}

export default function RulesManager() {
  const [editRule, setEditRule] = useState<Rule | null>(null)
  const [isFormOpen, setIsFormOpen] = useState(false)
  const queryClient = useQueryClient()
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: async () => (await getRules()).data,
    staleTime: 5 * 60 * 1000,
  })

  const isMobile = useIsMobile()

  const selectedWebsites = form.watch('website')
  const selectedSections = form.watch('section')
  const selectedDownloader = form.watch('downloader')
  const selectedCategories = form.watch('category')

  const { data: categoryTree } = useQuery({
    queryKey: ['article-category-tree'],
    queryFn: async () => (await getCategories()).data,
    staleTime: 5 * 60 * 1000,
  })

  const { data: downloaders } = useQuery({
    queryKey: ['downloaders'],
    queryFn: async () => (await fetchDownloaderList()).data,
    staleTime: 5 * 60 * 1000,
  })

  const websiteOptions = useMemo(
    () =>
      (categoryTree ?? []).map((item: WebsiteCategoryTree) => ({
        value: item.name,
        label: item.name,
        count: item.count,
      })),
    [categoryTree]
  )

  const scopedSections = useMemo(
    () =>
      flattenSectionsByWebsite(
        categoryTree ?? [],
        selectedWebsites.includes(ALL_VALUE) ? undefined : selectedWebsites
      ),
    [categoryTree, selectedWebsites]
  )

  const sectionOptions = useMemo(
    () =>
      scopedSections.map((item) => ({
        value: item.name,
        label: item.name,
        count: item.count,
      })),
    [scopedSections]
  )

  const categoryOptions = useMemo(
    () => buildCategoryOptions(scopedSections, selectedSections),
    [scopedSections, selectedSections]
  )

  const savePaths =
    downloaders?.find((item) => item.id === selectedDownloader)?.save_paths ??
    []

  useEffect(() => {
    if (editRule) {
      form.reset(editRule)
      return
    }
    if (isFormOpen) {
      form.reset(defaultValues)
    }
  }, [editRule, form, isFormOpen])

  useEffect(() => {
    const availableSections = new Set(sectionOptions.map((item) => item.value))
    if (!selectedSections.includes(ALL_VALUE)) {
      const filteredSections = selectedSections.filter((item) =>
        availableSections.has(item)
      )
      if (filteredSections.length !== selectedSections.length) {
        form.setValue(
          'section',
          filteredSections.length > 0 ? filteredSections : [ALL_VALUE],
          { shouldDirty: true }
        )
        return
      }
    }

    const availableCategories = new Set(
      categoryOptions.map((item) => item.value)
    )
    if (selectedCategories.includes(ALL_VALUE)) {
      return
    }
    const filteredCategories = selectedCategories.filter((item) =>
      availableCategories.has(item)
    )
    if (filteredCategories.length !== selectedCategories.length) {
      form.setValue(
        'category',
        filteredCategories.length > 0 ? filteredCategories : [ALL_VALUE],
        { shouldDirty: true }
      )
    }
  }, [
    categoryOptions,
    form,
    sectionOptions,
    selectedCategories,
    selectedSections,
  ])

  const handleDelete = async (id: number) => {
    const res = await deleteRule(id)
    if (res.code === 0) {
      toast.success(res.message)
      queryClient.invalidateQueries({ queryKey: ['rules'] })
    }
  }

  const handleSubmit = async (values: FormValues) => {
    const payload: Rule = {
      ...values,
      regex: values.regex.trim(),
    }
    const res = editRule ? await updateRule(payload) : await addRule(payload)
    if (res.code === 0) {
      toast.success(res.message)
      queryClient.invalidateQueries({ queryKey: ['rules'] })
      setIsFormOpen(false)
    }
  }

  return (
    <>
      <Dialog open={isFormOpen} onOpenChange={setIsFormOpen}>
        <DialogOverlay className='bg-background/20 backdrop-blur-lg' />
        <DialogTrigger asChild>
          <Button onClick={() => setEditRule(null)} variant='outline'>
            <Scale />
            创建秩序
          </Button>
        </DialogTrigger>
        <DialogContent className='bg-background/40 backdrop-blur-lg sm:max-w-xl'>
          <DialogHeader>
            <DialogTitle>{editRule ? '编辑秩序' : '创建秩序'}</DialogTitle>
          </DialogHeader>
          <Form {...form}>
            <form
              onSubmit={form.handleSubmit(handleSubmit)}
              className='space-y-4'
            >
              <FormField
                control={form.control}
                name='website'
                render={({ field }) => (
                  <MultiSelectField
                    label='站点'
                    value={field.value}
                    options={websiteOptions}
                    onChange={field.onChange}
                    placeholder='选择站点'
                    emptyText='没有匹配的站点'
                  />
                )}
              />
              <FormField
                control={form.control}
                name='section'
                render={({ field }) => (
                  <MultiSelectField
                    label='板块'
                    value={field.value}
                    options={sectionOptions}
                    onChange={field.onChange}
                    placeholder='选择板块'
                    emptyText='没有匹配的板块'
                  />
                )}
              />
              <FormField
                control={form.control}
                name='category'
                render={({ field }) => (
                  <MultiSelectField
                    label='分类'
                    value={field.value}
                    options={categoryOptions}
                    onChange={field.onChange}
                    placeholder='选择分类'
                    emptyText='没有匹配的分类'
                  />
                )}
              />
              <FormField
                control={form.control}
                name='regex'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel className='flex items-center gap-2'>
                      <Regex className='size-4' />
                      匹配正则（可选）
                    </FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        placeholder='^[A-Z]{3,5}-\\d{3,4}$'
                        className='font-mono'
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name='downloader'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>下载器</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger className='w-full'>
                          <SelectValue placeholder='选择下载器' />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent className='bg-background/20 backdrop-blur-md'>
                        {downloaders?.map((item) => (
                          <SelectItem key={item.id} value={item.id}>
                            {item.id}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name='save_path'
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>保存路径</FormLabel>
                    <Select
                      value={field.value}
                      disabled={!selectedDownloader}
                      onValueChange={field.onChange}
                    >
                      <FormControl>
                        <SelectTrigger className='w-full'>
                          <SelectValue placeholder='选择保存路径' />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent className='bg-background/20 backdrop-blur-md'>
                        {savePaths.map((item) => (
                          <SelectItem key={item.path} value={item.path}>
                            {item.path}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type='submit' className='w-full'>
                提交
              </Button>
            </form>
          </Form>
        </DialogContent>
      </Dialog>
      {isMobile ? (
        <RuleTableMobile
          data={data}
          onEdit={(item) => {
            setEditRule(item)
            setIsFormOpen(true)
          }}
          onDelete={handleDelete}
          isLoading={isLoading}
        />
      ) : (
        <RuleTableDesktop
          data={data}
          onEdit={(item) => {
            setEditRule(item)
            setIsFormOpen(true)
          }}
          onDelete={handleDelete}
          isLoading={isLoading}
        />
      )}
    </>
  )
}
