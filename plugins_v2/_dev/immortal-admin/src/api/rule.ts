import { request } from '@/api/request.ts'

export interface Rule {
  id: number
  website: string[]
  section: string[]
  category: string[]
  regex: string
  downloader: string
  save_path: string
}

export interface RuleCategoryOption {
  name: string
  count: number
}

export interface RuleSectionOption {
  name: string
  count: number
  categories?: RuleCategoryOption[]
}

export interface RuleWebsiteOption {
  name: string
  count: number
}

export interface RuleOptionsResult {
  websites: RuleWebsiteOption[]
  sections: RuleSectionOption[]
}

export function getRules() {
  return request<Rule[]>({ url: '/rules/' })
}

export function getRuleOptions(params?: { website?: string[] }) {
  return request<RuleOptionsResult>({
    url: '/rules/options',
    params: {
      website: params?.website?.length ? params.website.join(',') : undefined,
    },
  })
}

export function addRule(data: Rule) {
  return request({ url: '/rules/', method: 'post', data })
}

export function updateRule(data: Rule) {
  return request({ url: '/rules/', method: 'put', data })
}

export function deleteRule(rule_id: number) {
  return request({ url: `/rules/${rule_id}`, method: 'delete' })
}
