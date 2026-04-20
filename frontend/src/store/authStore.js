import { create } from 'zustand'
import api from '../api/client'

const useAuthStore = create((set) => ({
  user: null,
  loading: true,

  fetchProfile: async () => {
    try {
      const { data } = await api.get('/auth/profile')
      set({ user: data, loading: false })
    } catch {
      set({ user: null, loading: false })
    }
  },

  login: async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const profile = await api.get('/auth/profile')
    set({ user: profile.data })
  },

  register: async (email, username, password) => {
    const { data } = await api.post('/auth/register', { email, username, password })
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    const profile = await api.get('/auth/profile')
    set({ user: profile.data })
  },

  logout: () => {
    localStorage.clear()
    set({ user: null })
  },

  updateCredits: (credits, free_credits) => set((s) => ({
    user: s.user ? { ...s.user, credits: credits ?? s.user.credits, free_credits: free_credits ?? s.user.free_credits } : null,
  })),
}))

export default useAuthStore
