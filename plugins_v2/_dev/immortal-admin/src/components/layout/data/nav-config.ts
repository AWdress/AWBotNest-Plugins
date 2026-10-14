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
import { useAuthStore } from '@/stores/auth-store.ts'
import { useUIStore } from '@/stores/ui-store'
import { type SidebarData } from '../types'

const { auth } = useAuthStore.getState()

// 仙侠版导航数据
const fantasySidebarData: SidebarData = {
  user: {
    name: auth.username,
  },
  navGroups: [
    {
      title: '洞府中枢',
      items: [
        { title: '观星台', url: '/', icon: Mountain },
        {
          title: '时轮殿',
          icon: Clock3,
          items: [
            { url: '/tasks', title: '阵令', icon: BookCheck },
            { url: '/tasks/log', title: '运转录', icon: Clock3 },
          ],
        },
        {
          title: '天榜',
          icon: Trophy,
          url: '/rank/movie',
        },
        { title: '历练录', url: '/download-log', icon: Swords },
        {
          title: '灵契簿',
          icon: Heart,
          url: '/subscribes',
        },
        { title: '巡天鉴', url: '/subscribes/search', icon: Compass },
        { title: '藏经阁', url: '/articles', icon: ScrollText },
      ],
    },
    {
      title: '仙府内务',
      items: [
        { title: '灵枢阁', url: '/sub-config', icon: WandSparkles },
        { title: '道枢', url: '/settings', icon: Shield },
        { title: '问道台', url: '/help-center', icon: HelpCircle },
      ],
    },
  ],
}

// 通俗版导航数据
const simpleSidebarData: SidebarData = {
  user: {
    name: auth.username,
  },
  navGroups: [
    {
      title: '首页',
      items: [
        { title: '仪表盘', url: '/', icon: LayoutDashboard },
        {
          title: '任务管理',
          icon: ListChecks,
          items: [
            { url: '/tasks', title: '任务列表', icon: BookCheck },
            { url: '/tasks/log', title: '任务日志', icon: Clock3 },
          ],
        },
        {
          title: '排行榜',
          icon: Trophy,
          url: '/rank/movie',
        },
        { title: '下载日志', url: '/download-log', icon: Download },
        {
          title: '订阅管理',
          icon: Heart,
          url: '/subscribes',
        },
        { title: '订阅搜索', url: '/subscribes/search', icon: Search },
        { title: '文章管理', url: '/articles', icon: Newspaper },
      ],
    },
    {
      title: '系统',
      items: [
        { title: '订阅配置', url: '/sub-config', icon: WandSparkles },
        { title: '系统设置', url: '/settings', icon: Settings },
        { title: '帮助中心', url: '/help-center', icon: HelpCircle },
      ],
    },
  ],
}

export function useSidebarData(): SidebarData {
  const routeNamingMode = useUIStore((state) => state.routeNamingMode)
  return routeNamingMode === 'simple' ? simpleSidebarData : fantasySidebarData
}

export { fantasySidebarData, simpleSidebarData }
