import { useRef, useState, useEffect } from 'react'
import { Play, Pause, X, Download } from 'lucide-react'
import usePlayerStore from '../store/playerStore'

export default function GlobalPlayer() {
  const { currentTrack, playing, pause, resume, stop } = usePlayerStore()
  const audioRef = useRef(null)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)

  // Sync play/pause with store
  useEffect(() => {
    if (!audioRef.current) return
    if (playing) audioRef.current.play().catch(() => {})
    else audioRef.current.pause()
  }, [playing])

  // When track changes, load and play
  useEffect(() => {
    if (!audioRef.current || !currentTrack) return
    audioRef.current.load()
    audioRef.current.play().catch(() => {})
    setProgress(0)
    setDuration(0)
  }, [currentTrack?.url])

  const onTimeUpdate = () => {
    if (!audioRef.current) return
    setProgress(audioRef.current.currentTime)
    setDuration(audioRef.current.duration || 0)
  }

  const seek = (e) => {
    if (!audioRef.current || !duration) return
    const rect = e.currentTarget.getBoundingClientRect()
    const pct = (e.clientX - rect.left) / rect.width
    audioRef.current.currentTime = pct * duration
  }

  const fmt = (s) => {
    if (!s || isNaN(s)) return '0:00'
    const m = Math.floor(s / 60)
    const sec = Math.floor(s % 60)
    return `${m}:${sec.toString().padStart(2, '0')}`
  }

  if (!currentTrack) return null

  return (
    <div className="fixed bottom-0 left-64 right-0 z-50 px-6 pb-4">
      <div className="neu-card-flat p-3 flex items-center gap-4" style={{ backdropFilter: 'blur(12px)', background: 'rgba(238,241,245,0.95)' }}>
        <audio
          ref={audioRef}
          src={currentTrack.url}
          onTimeUpdate={onTimeUpdate}
          onEnded={() => pause()}
          onLoadedMetadata={onTimeUpdate}
        />

        {/* Play / Pause */}
        <button onClick={() => playing ? pause() : resume()} className="neu-btn p-2.5 rounded-full flex-shrink-0">
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </button>

        {/* Track info + progress */}
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-text truncate mb-1">{currentTrack.title || '播放中'}</p>
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted w-10 text-right flex-shrink-0">{fmt(progress)}</span>
            <div className="flex-1 h-1.5 rounded-full cursor-pointer" style={{ boxShadow: 'var(--shadow-neu-inset)', background: 'var(--color-surface)' }} onClick={seek}>
              <div
                className="h-full rounded-full transition-all duration-100"
                style={{ width: `${duration ? (progress / duration) * 100 : 0}%`, background: 'linear-gradient(90deg, var(--color-primary), var(--color-accent))' }}
              />
            </div>
            <span className="text-xs text-text-muted w-10 flex-shrink-0">{fmt(duration)}</span>
          </div>
        </div>

        {/* Download */}
        <a href={currentTrack.url} download className="neu-btn p-2 rounded-full flex-shrink-0">
          <Download size={16} />
        </a>

        {/* Close */}
        <button onClick={stop} className="neu-btn p-2 rounded-full flex-shrink-0">
          <X size={16} />
        </button>
      </div>
    </div>
  )
}
