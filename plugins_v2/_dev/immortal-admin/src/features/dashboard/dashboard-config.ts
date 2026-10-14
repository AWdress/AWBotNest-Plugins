export const DASHBOARD_CONFIG_KEY = 'DashboardConfig'
export const DASHBOARD_CONFIG_QUERY_KEY = [DASHBOARD_CONFIG_KEY] as const

export const DASHBOARD_SECTION_DEFINITIONS = [
  {
    key: 'download_dashboard',
    title: '下载总览',
    description: '下载量、版块分布和灵根图表',
  },
  {
    key: 'summary_cards',
    title: '汇总卡片',
    description: '总分类数、总资源数和当前境界',
  },
  {
    key: 'recent_release_subscribes',
    title: '近日发售待入库',
    description: '展示一周内发售且未入库的订阅影片',
  },
  {
    key: 'subscription_recommendations',
    title: '订阅推荐',
    description: '根据已订阅影片推荐相近内容',
  },
  {
    key: 'movie_frequency_stats',
    title: '影片频次趋势',
    description: '演员、制作商和系列的 Top 10 统计',
  },
  {
    key: 'category_cards',
    title: '分类面板',
    description: '展示各分类资源数量概览',
  },
] as const

export type DashboardSectionKey =
  (typeof DASHBOARD_SECTION_DEFINITIONS)[number]['key']

export interface DashboardConfigPayload {
  sections: DashboardSectionKey[]
}

export const DEFAULT_DASHBOARD_SECTIONS: DashboardSectionKey[] =
  DASHBOARD_SECTION_DEFINITIONS.map((item) => item.key)

export function resolveDashboardSections(
  payload?: DashboardConfigPayload | null
): DashboardSectionKey[] {
  if (!payload || !Array.isArray(payload.sections)) {
    return DEFAULT_DASHBOARD_SECTIONS
  }

  const allowed = new Set(DEFAULT_DASHBOARD_SECTIONS)
  const uniqueSections: DashboardSectionKey[] = []
  for (const key of payload.sections) {
    if (!allowed.has(key) || uniqueSections.includes(key)) {
      continue
    }
    uniqueSections.push(key)
  }
  return uniqueSections
}

export function isDashboardSectionVisible(
  sections: DashboardSectionKey[],
  key: DashboardSectionKey
) {
  return sections.includes(key)
}
