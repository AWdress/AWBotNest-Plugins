import { create } from 'zustand'

// Authentication belongs to AWBotNest. No tokens or credential cookies enter this iframe.
export const useAuthStore = create(() => ({ auth: { username: '平台管理员' } }))
