import { useRef, useState, useEffect } from 'react'
import { Play, Pause, Download, Volume2 } from 'lucide-react'

export default function AudioPlayer({ src, title }) {
  const audioRef = useRef(null)
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(0)
  const [duration, setDuration] = useState(0)

  useEffect(() => {
    setPlaying(false)
    setProgress(0)
  }, [src])

  const toggle = () => {
    if (!audioRef.current) return
    if (playing) { audioRef.current.pause() } else { audioRef.current.play() }
    setPlaying(!playing)
  }

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

  if (!src) return null

  return (
    <div className="neu-card-flat p-4 animate-fade-in">
      <audio ref={audioRef} src={src} onTimeUpdate={onTimeUpdate} onEnded={() => setPlaying(false)} onLoadedMetadata={onTimeUpdate} />
      {title && <p className="text-sm font-medium mb-3 text-text">{title}</p>}
      <div className="flex items-center gap-3">
        <button onClick={toggle} className="neu-btn p-3 rounded-full flex-shrink-0">
          {playing ? <Pause size={18} /> : <Play size={18} />}
        </button>
        <div className="flex-1">
          <div className="h-2 rounded-full cursor-pointer" style={{ boxShadow: 'var(--shadow-neu-inset)', background: 'var(--color-surface)' }} onClick={seek}>
            <div
              className="h-full rounded-full transition-all duration-100"
              style={{ width: `${duration ? (progress / duration) * 100 : 0}%`, background: 'linear-gradient(90deg, var(--color-primary), var(--color-accent))' }}
            />
          </div>
          <div className="flex justify-between mt-1 text-xs text-text-muted">
            <span>{fmt(progress)}</span>
            <span>{fmt(duration)}</span>
          </div>
        </div>
        <a href={src} download className="neu-btn p-2.5 rounded-full flex-shrink-0">
          <Download size={16} />
        </a>
      </div>
    </div>
  )
}
