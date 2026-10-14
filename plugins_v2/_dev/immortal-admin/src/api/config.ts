import { request } from './request'

export interface SavePath {
  path: string
  label: string
}

export interface Downloader {
  id: string
  save_paths: SavePath[]
}

export function getConfig<T>(key: string) {
  return request<T>({
    url: `/config/${key}`,
    method: 'get',
  })
}

export function deleteConfig(key: string) {
  return request({
    url: `/config/${key}`,
    method: 'delete',
  })
}

export function postConfig(key: string, data: never) {
  return request({
    url: `/config/`,
    method: 'post',
    data: {
      key: key,
      payload: data,
    },
  })
}

export function fetchDownloaderList() {
  return request<Downloader[]>({
    url: `/config/downloaders`,
    method: 'get',
  })
}
