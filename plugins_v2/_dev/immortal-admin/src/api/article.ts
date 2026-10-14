import axios from './axios'
import { request } from './request'

export interface Article {
  id: number
  title: string
  section: string
  publish_date: string
  magnet: string[]
  edk: string[]
  img_list: string[]
  category: string
  size: number
  in_stock: boolean
  in_library?: boolean
  detail_url: string
  website: string
}

export interface ArticleFilter {
  page: number
  page_size: number
  keyword: string
  website: string
  section: string
  category: string
  date_range: { from: string; to: string }
}

export interface ArticleListResult {
  items: Article[]
  total: number
  hasMore: boolean
  page: number
  pageSize: number
}

export interface Category {
  name: string
  count: number
}

export interface Section {
  name: string
  count: number
  categories?: Category[]
}

export interface WebsiteCategoryTree {
  name: string
  count: number
  sections?: Section[]
}

export interface UploadResult {
  inserted: number
  skipped: number
}

export function getArticles(data: ArticleFilter) {
  return request<ArticleListResult>({
    url: '/articles/search',
    method: 'post',
    data,
  })
}

export function getCategories() {
  return request<WebsiteCategoryTree[]>({ url: '/articles/categories' })
}

export function flattenSectionsByWebsite(
  websites: WebsiteCategoryTree[],
  website?: string | string[]
): Section[] {
  const sectionMap = new Map<
    string,
    { count: number; categories: Map<string, number> }
  >()
  const allowedWebsites = Array.isArray(website)
    ? website.filter(Boolean)
    : website
      ? [website]
      : []
  const rows =
    allowedWebsites.length > 0
      ? websites.filter((item) => allowedWebsites.includes(item.name))
      : websites

  rows.forEach((site) => {
    site.sections?.forEach((section) => {
      const target = sectionMap.get(section.name) ?? {
        count: 0,
        categories: new Map<string, number>(),
      }
      target.count += section.count
      section.categories?.forEach((category) => {
        target.categories.set(
          category.name,
          (target.categories.get(category.name) ?? 0) + category.count
        )
      })
      sectionMap.set(section.name, target)
    })
  })

  return [...sectionMap.entries()]
    .sort((a, b) => b[1].count - a[1].count || a[0].localeCompare(b[0]))
    .map(([name, payload]) => ({
      name,
      count: payload.count,
      categories: [...payload.categories.entries()]
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
        .map(([categoryName, count]) => ({ name: categoryName, count })),
    }))
}

export function flattenSectionTotals(
  websites: WebsiteCategoryTree[]
): Section[] {
  return flattenSectionsByWebsite(websites)
}

export function downloadArticle(article_id: number) {
  return request({ url: '/articles/download', params: { article_id } })
}

export function manulDownloadArticle(
  article_id: number,
  downloader: string,
  savePath: string
) {
  return request({
    url: '/articles/download/manul',
    params: { article_id, downloader, save_path: savePath },
  })
}

export function batchDownloadArticle(article_id_list: string) {
  return request({
    url: '/articles/download/batch',
    params: { article_id_list },
  })
}

export function batchManulDownloadArticle(
  article_id_list: string,
  downloader: string,
  savePath: string
) {
  return request({
    url: '/articles/download/manul/batch',
    params: { article_id_list, downloader, save_path: savePath },
  })
}

export function uploadArticle(
  file: File,
  onProgress?: (percent: number) => void
) {
  const formData = new FormData()
  formData.append('file', file)
  return request<UploadResult>({
    url: '/articles/import/excel',
    method: 'post',
    data: formData,
    onUploadProgress: (e) => {
      if (!e.total) return
      const percent = Math.round((e.loaded / e.total) * 100)
      onProgress?.(percent)
    },
  })
}

export async function downloadData() {
  const response = await axios.get('/articles/export/excel', {
    responseType: 'blob',
  })
  const blob = response.data instanceof Blob ? response.data : new Blob([response.data], { type: 'text/csv;charset=utf-8' })

  const link = document.createElement('a')
  link.href = window.URL.createObjectURL(blob)
  link.download = '文章数据.csv'
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => window.URL.revokeObjectURL(link.href), 1000)
}
