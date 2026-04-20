import { create } from 'zustand'

const usePlayerStore = create((set) => ({
  currentTrack: null, // { url, title }
  playing: false,

  play: (url, title) => set({ currentTrack: { url, title }, playing: true }),
  pause: () => set({ playing: false }),
  resume: () => set({ playing: true }),
  stop: () => set({ currentTrack: null, playing: false }),
}))

export default usePlayerStore
