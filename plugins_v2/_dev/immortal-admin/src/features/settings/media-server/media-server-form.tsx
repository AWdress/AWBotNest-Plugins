import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { toast } from 'sonner'

import { getConfig, postConfig } from '@/api/config.ts'
import { Button } from '@/components/ui/button.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Label } from '@/components/ui/label.tsx'
import { Separator } from '@/components/ui/separator.tsx'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs.tsx'

type EmbyConfig = {
  url: string
  api_key: string
}

type JellyfinConfig = {
  url: string
  api_key: string
  user_id?: string
}

type PlexConfig = {
  url: string
  token: string
  library_id?: string
}

type ZSpaceConfig = {
  url: string
  cookie: string
}

const EMBY_KEY = 'MediaServer.emby'
const JELLYFIN_KEY = 'MediaServer.jellyfin'
const PLEX_KEY = 'MediaServer.plex'
const ZSPACE_KEY = 'MediaServer.zspace'
const EMBY_QUERY_KEY = [EMBY_KEY] as const
const JELLYFIN_QUERY_KEY = [JELLYFIN_KEY] as const
const PLEX_QUERY_KEY = [PLEX_KEY] as const
const ZSPACE_QUERY_KEY = [ZSPACE_KEY] as const

export function MediaServerForm() {
  const queryClient = useQueryClient()
  const [emby, setEmby] = useState<EmbyConfig>({
    url: '',
    api_key: '',
  })
  const [jellyfin, setJellyfin] = useState<JellyfinConfig>({
    url: '',
    api_key: '',
    user_id: '',
  })
  const [plex, setPlex] = useState<PlexConfig>({
    url: '',
    token: '',
    library_id: '',
  })
  const [zspace, setZspace] = useState<ZSpaceConfig>({
    url: '',
    cookie: '',
  })

  const embyQuery = useQuery({
    queryKey: EMBY_QUERY_KEY,
    queryFn: async () => {
      const res = await getConfig<EmbyConfig>(EMBY_KEY)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const jellyfinQuery = useQuery({
    queryKey: JELLYFIN_QUERY_KEY,
    queryFn: async () => {
      const res = await getConfig<JellyfinConfig>(JELLYFIN_KEY)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const plexQuery = useQuery({
    queryKey: PLEX_QUERY_KEY,
    queryFn: async () => {
      const res = await getConfig<PlexConfig>(PLEX_KEY)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const zspaceQuery = useQuery({
    queryKey: ZSPACE_QUERY_KEY,
    queryFn: async () => {
      const res = await getConfig<ZSpaceConfig>(ZSPACE_KEY)
      return res.data
    },
    staleTime: 5 * 60 * 1000,
  })

  const loading = embyQuery.isFetching || jellyfinQuery.isFetching || plexQuery.isFetching || zspaceQuery.isFetching

  useEffect(() => {
    if (embyQuery.data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEmby({
        url: embyQuery.data.url || '',
        api_key: embyQuery.data.api_key || '',
      })
    }
  }, [embyQuery.data])

  useEffect(() => {
    if (jellyfinQuery.data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setJellyfin({
        url: jellyfinQuery.data.url || '',
        api_key: jellyfinQuery.data.api_key || '',
        user_id: jellyfinQuery.data.user_id || '',
      })
    }
  }, [jellyfinQuery.data])

  useEffect(() => {
    if (plexQuery.data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPlex({
        url: plexQuery.data.url || '',
        token: plexQuery.data.token || '',
        library_id: plexQuery.data.library_id || '',
      })
    }
  }, [plexQuery.data])

  useEffect(() => {
    if (zspaceQuery.data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setZspace({
        url: zspaceQuery.data.url || '',
        cookie: zspaceQuery.data.cookie || '',
      })
    }
  }, [zspaceQuery.data])

  const handleSave = async <T extends object>(key: string, queryKey: readonly string[], payload: T) => {
    try {
      const res = await postConfig(key, payload as never)
      await queryClient.invalidateQueries({ queryKey, exact: true })
      toast.success(res.message || '保存成功')
    } catch (e) {
      toast.error('保存失败')
    }
  }

  return (
    <Tabs defaultValue='emby' className='w-full'>
      <TabsList>
        <TabsTrigger value='emby'>Emby</TabsTrigger>
        <TabsTrigger value='jellyfin'>Jellyfin</TabsTrigger>
        <TabsTrigger value='plex'>Plex</TabsTrigger>
        <TabsTrigger value='zspace'>极影视</TabsTrigger>
      </TabsList>
      <Separator />

      <TabsContent value='emby'>
        <div className='mt-4 max-w-xl space-y-4'>
          <div className='space-y-2'>
            <Label htmlFor='emby-url'>服务地址</Label>
            <Input
              id='emby-url'
              placeholder='例如：http://127.0.0.1:8096'
              value={emby.url}
              onChange={(e) =>
                setEmby((prev) => ({ ...prev, url: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='emby-api'>API Key</Label>
            <Input
              id='emby-api'
              type='password'
              value={emby.api_key}
              onChange={(e) =>
                setEmby((prev) => ({ ...prev, api_key: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <Button
            type='button'
            onClick={() => handleSave(EMBY_KEY, EMBY_QUERY_KEY, emby)}
            disabled={loading}
          >
            <Save className='mr-2 h-4 w-4' />
            保存 Emby 配置
          </Button>
        </div>
      </TabsContent>

      <TabsContent value='jellyfin'>
        <div className='mt-4 max-w-xl space-y-4'>
          <div className='space-y-2'>
            <Label htmlFor='jellyfin-url'>服务地址</Label>
            <Input
              id='jellyfin-url'
              placeholder='例如：http://127.0.0.1:8096'
              value={jellyfin.url}
              onChange={(e) =>
                setJellyfin((prev) => ({ ...prev, url: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='jellyfin-api'>API Key</Label>
            <Input
              id='jellyfin-api'
              type='password'
              value={jellyfin.api_key}
              onChange={(e) =>
                setJellyfin((prev) => ({ ...prev, api_key: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='jellyfin-user-id'>用户 ID（可选）</Label>
            <Input
              id='jellyfin-user-id'
              placeholder='设置后只查询该用户的媒体库'
              value={jellyfin.user_id}
              onChange={(e) =>
                setJellyfin((prev) => ({ ...prev, user_id: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <Button
            type='button'
            onClick={() => handleSave(JELLYFIN_KEY, JELLYFIN_QUERY_KEY, jellyfin)}
            disabled={loading}
          >
            <Save className='mr-2 h-4 w-4' />
            保存 Jellyfin 配置
          </Button>
        </div>
      </TabsContent>

      <TabsContent value='plex'>
        <div className='mt-4 max-w-xl space-y-4'>
          <div className='space-y-2'>
            <Label htmlFor='plex-url'>服务地址</Label>
            <Input
              id='plex-url'
              placeholder='例如：http://127.0.0.1:32400'
              value={plex.url}
              onChange={(e) =>
                setPlex((prev) => ({ ...prev, url: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='plex-token'>Token</Label>
            <Input
              id='plex-token'
              type='password'
              value={plex.token}
              onChange={(e) =>
                setPlex((prev) => ({ ...prev, token: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='plex-library-id'>电影库 ID（可选）</Label>
            <Input
              id='plex-library-id'
              placeholder='Plex 电影库 section id'
              value={plex.library_id}
              onChange={(e) =>
                setPlex((prev) => ({
                  ...prev,
                  library_id: e.target.value,
                }))
              }
              disabled={loading}
            />
          </div>
          <Button
            type='button'
            onClick={() => handleSave(PLEX_KEY, PLEX_QUERY_KEY, plex)}
            disabled={loading}
          >
            <Save className='mr-2 h-4 w-4' />
            保存 Plex 配置
          </Button>
        </div>
      </TabsContent>

      <TabsContent value='zspace'>
        <div className='mt-4 max-w-xl space-y-4'>
          <div className='space-y-2'>
            <Label htmlFor='zspace-url'>服务地址</Label>
            <Input
              id='zspace-url'
              type='text'
              placeholder='例如：http://127.0.0.1:5055'
              value={zspace.url}
              onChange={(e) =>
                setZspace((prev) => ({ ...prev, url: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <div className='space-y-2'>
            <Label htmlFor='zspace-cookie'>Cookie</Label>
            <Input
              id='zspace-cookie'
              type='text'
              placeholder='填写从极空间web或者客户端获取的cookie'
              value={zspace.cookie}
              onChange={(e) =>
                setZspace((prev) => ({ ...prev, cookie: e.target.value }))
              }
              disabled={loading}
            />
          </div>
          <Button
            type='button'
            onClick={() => handleSave(ZSPACE_KEY, ZSPACE_QUERY_KEY, zspace)}
            disabled={loading}
          >
            <Save className='mr-2 h-4 w-4' />
            保存极影视配置
          </Button>
        </div>
      </TabsContent>
    </Tabs>
  )
}
