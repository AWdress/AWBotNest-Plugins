import {
  BookCheck,
  Clock3,
  Compass,
  Heart,
  HelpCircle,
  Mountain,
  ScrollText,
  Shield,
  Swords,
  Trophy,
  WandSparkles,
} from 'lucide-react'
import { useAuthStore } from '@/stores/auth-store.ts'
import { type SidebarData } from '../types'

const { auth } = useAuthStore.getState()
export const sidebarData: SidebarData = {
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
