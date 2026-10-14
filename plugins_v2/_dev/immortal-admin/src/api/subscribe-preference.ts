import { getConfig, postConfig } from '@/api/config.ts'

export interface SubscribePreferenceConfig {
  earliest_release_date?: string | null
  exclude_vr: boolean
  max_coactors?: number | null
  max_page?: number | null
  replace_max_page?: number | null
  is_single: boolean
  number_prefix_blacklist: string[]
  keyword_blacklist: string[]
}

export const SUBSCRIBE_PREFERENCE_CONFIG_KEY = 'SubscribePreferenceConfig'
export const SUBSCRIBE_PREFERENCE_CONFIG_QUERY_KEY = [
  SUBSCRIBE_PREFERENCE_CONFIG_KEY,
] as const

export const DEFAULT_SUBSCRIBE_PREFERENCE_CONFIG: SubscribePreferenceConfig = {
  earliest_release_date: null,
  exclude_vr: false,
  max_coactors: null,
  max_page: null,
  replace_max_page: null,
  is_single: false,
  number_prefix_blacklist: [],
  keyword_blacklist: [],
}

export function getSubscribePreferenceConfig() {
  return getConfig<SubscribePreferenceConfig>(SUBSCRIBE_PREFERENCE_CONFIG_KEY)
}

export function saveSubscribePreferenceConfig(
  payload: SubscribePreferenceConfig
) {
  return postConfig(SUBSCRIBE_PREFERENCE_CONFIG_KEY, payload as never)
}
