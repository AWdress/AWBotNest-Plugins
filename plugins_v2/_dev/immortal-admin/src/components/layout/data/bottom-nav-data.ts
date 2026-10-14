import {
  BookCheck,
  Clock3,
  Compass,
  Download,
  Heart,
  HelpCircle,
  LayoutDashboard,
  ListChecks,
  Mountain,
  Newspaper,
  ScrollText,
  Search,
  Settings,
  Shield,
  Swords,
  Trophy,
  WandSparkles,
} from 'lucide-react'
import { useUIStore } from '@/stores/ui-store'

export const fantasyMainNavItems = [
  {
    id: 'dashboard',
    label: '观星台',
    url: '/',
    icon: Mountain,
  },
  {
    id: 'articles',
    label: '藏经阁',
    url: '/articles',
    icon: ScrollText,
  },
  {
    id: 'subscribes',
    url: '/subscribes',
    label: '灵契簿',
    icon: Heart,
  },
  { id: 'rank-overview', url: '/rank/movie', label: '天榜', icon: Trophy },
]

export const simpleMainNavItems = [
  {
    id: 'dashboard',
    label: '仪表盘',
    url: '/',
    icon: LayoutDashboard,
  },
  {
    id: 'articles',
    label: '文章',
    url: '/articles',
    icon: Newspaper,
  },
  {
    id: 'subscribes',
    url: '/subscribes',
    label: '订阅',
    icon: Heart,
  },
  { id: 'rank-overview', url: '/rank/movie', label: '排行', icon: Trophy },
]

export const fantasyMoreMenuItems = [
  {
    title: '天机阁',
    items: [
      {
        id: 'database-search',
        url: '/subscribes/search',
        label: '巡天鉴',
        icon: Compass,
      },
    ],
  },
  {
    title: '时轮殿',
    items: [
      {
        id: 'tasks',
        label: '阵令',
        url: '/tasks',
        icon: BookCheck,
      },
      {
        id: 'tasks-log',
        label: '运转录',
        url: '/tasks/log',
        icon: Clock3,
      },
    ],
  },
  {
    title: '仙府内务',
    items: [
      {
        id: 'sub-config',
        label: '灵枢阁',
        url: '/sub-config',
        icon: WandSparkles,
      },
      {
        id: 'download-log',
        label: '历练录',
        url: '/download-log',
        icon: Swords,
      },
      {
        id: 'settings',
        label: '道枢',
        url: '/settings',
        icon: Shield,
      },
      {
        id: 'help',
        label: '问道台',
        url: '/help-center',
        icon: HelpCircle,
      },
    ],
  },
]

export const simpleMoreMenuItems = [
  {
    title: '工具',
    items: [
      {
        id: 'database-search',
        url: '/subscribes/search',
        label: '搜索',
        icon: Search,
      },
    ],
  },
  {
    title: '任务',
    items: [
      {
        id: 'tasks',
        label: '任务列表',
        url: '/tasks',
        icon: ListChecks,
      },
      {
        id: 'tasks-log',
        label: '任务日志',
        url: '/tasks/log',
        icon: Clock3,
      },
    ],
  },
  {
    title: '系统',
    items: [
      {
        id: 'sub-config',
        label: '订阅配置',
        url: '/sub-config',
        icon: WandSparkles,
      },
      {
        id: 'download-log',
        label: '下载日志',
        url: '/download-log',
        icon: Download,
      },
      {
        id: 'settings',
        label: '设置',
        url: '/settings',
        icon: Settings,
      },
      {
        id: 'help',
        label: '帮助',
        url: '/help-center',
        icon: HelpCircle,
      },
    ],
  },
]

export function useBottomNavData() {
  const routeNamingMode = useUIStore((state) => state.routeNamingMode)
  return {
    mainNavItems:
      routeNamingMode === 'simple' ? simpleMainNavItems : fantasyMainNavItems,
    moreMenuItems:
      routeNamingMode === 'simple' ? simpleMoreMenuItems : fantasyMoreMenuItems,
  }
}
