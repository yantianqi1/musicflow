import { useState, useEffect } from 'react'
import { FolderOpen, Music, Mic, FileText, Sparkles, Play, Copy, ExternalLink, Coins, Clock, ChevronLeft, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import api from '../../api/client'
import usePlayerStore from '../../store/playerStore'

const TABS = [
  { key: 'all', label: '全部', icon: FolderOpen },
  { key: 'music', label: '音乐', icon: Music },
  { key: 'speech', label: '语音', icon: Mic },
  { key: 'lyrics', label: '歌词', icon: FileText },
  { key: 'voice', label: '音色', icon: Sparkles },
]

const TYPE_LABELS = {
  music: '音乐',
  music_cover: '翻唱',
  speech_sync: '语音',
  speech_async: '长文本语音',
  lyrics: '歌词',
  voice_clone: '克隆音色',
  voice_design: '设计音色',
}

const TYPE_COLORS = {
  music: 'from-violet-500 to-purple-500',
  music_cover: 'from-pink-500 to-rose-400',
  speech_sync: 'from-emerald-500 to-teal-400',
  speech_async: 'from-emerald-500 to-teal-400',
  lyrics: 'from-blue-500 to-cyan-400',
  voice_clone: 'from-amber-500 to-orange-400',
  voice_design: 'from-amber-500 to-orange-400',
}

const EMPTY_HINTS = {
  all: { text: '还没有任何作品', link: '/agent', linkText: '去找 Lyra 创作' },
  music: { text: '还没有音乐作品', link: '/music/create', linkText: '去创作音乐' },
  speech: { text: '还没有语音作品', link: '/speech', linkText: '去语音合成' },
  lyrics: { text: '还没有歌词', link: '/music/create', linkText: '去生成歌词' },
  voice: { text: '还没有自定义音色', link: '/voice', linkText: '去声音工作室' },
}

function fmtDuration(ms) {
  if (!ms) return null
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${sec.toString().padStart(2, '0')}`
}

function fmtDate(isoStr) {
  const d = new Date(isoStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

// ─── Audio Card ───────────────────────────────────────────────
function AudioCard({ item }) {
  const play = usePlayerStore((s) => s.play)

  return (
    <div className="neu-card-flat p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-text truncate">{item.title || TYPE_LABELS[item.service_type]}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className={`inline-flex text-xs px-2 py-0.5 rounded-full text-white bg-gradient-to-r ${TYPE_COLORS[item.service_type]}`}>
              {TYPE_LABELS[item.service_type]}
            </span>
            <span className="text-xs text-text-muted">{fmtDate(item.created_at)}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 mt-3">
        {item.duration_ms && (
          <span className="text-xs text-text-muted flex items-center gap-1">
            <Clock size={12} /> {fmtDuration(item.duration_ms)}
          </span>
        )}
        <span className="text-xs text-text-muted flex items-center gap-1">
          <Coins size={12} /> {item.credits_cost}
        </span>
      </div>

      {item.result_url && (
        <div className="flex gap-2 mt-3">
          <button
            onClick={() => play(item.result_url, item.title || TYPE_LABELS[item.service_type])}
            className="neu-btn neu-btn-primary text-xs py-1.5 px-3 gap-1 flex-1"
          >
            <Play size={14} /> 播放
          </button>
        </div>
      )}
    </div>
  )
}

// ─── Lyrics Card ──────────────────────────────────────────────
function LyricsCard({ item }) {
  const [expanded, setExpanded] = useState(false)
  const [copied, setCopied] = useState(false)
  const lyrics = item.lyrics_text || ''
  const preview = lyrics.split('\n').slice(0, 4).join('\n')

  const handleCopy = () => {
    navigator.clipboard.writeText(lyrics).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="neu-card-flat p-4">
      <div className="flex items-start justify-between mb-2">
        <p className="text-sm font-medium text-text truncate flex-1">{item.title || '歌词'}</p>
        <span className={`inline-flex text-xs px-2 py-0.5 rounded-full text-white bg-gradient-to-r ${TYPE_COLORS.lyrics}`}>
          歌词
        </span>
      </div>

      <pre className="text-xs text-text-light whitespace-pre-wrap mt-2 leading-relaxed max-h-40 overflow-hidden" style={expanded ? { maxHeight: 'none' } : {}}>
        {expanded ? lyrics : preview}{!expanded && lyrics.split('\n').length > 4 && '...'}
      </pre>

      <div className="flex items-center gap-2 mt-3">
        {lyrics.split('\n').length > 4 && (
          <button onClick={() => setExpanded(!expanded)} className="neu-btn text-xs py-1.5 px-3">
            {expanded ? '收起' : '展开'}
          </button>
        )}
        <button onClick={handleCopy} className="neu-btn text-xs py-1.5 px-3 gap-1">
          <Copy size={12} /> {copied ? '已复制' : '复制'}
        </button>
        <span className="text-xs text-text-muted flex items-center gap-1 ml-auto">
          <Coins size={12} /> {item.credits_cost}
        </span>
        <span className="text-xs text-text-muted">{fmtDate(item.created_at)}</span>
      </div>
    </div>
  )
}

// ─── Voice Card ───────────────────────────────────────────────
function VoiceCard({ item }) {
  const [copied, setCopied] = useState(false)
  const isCloned = item.voice_type === 'cloned'

  const handleCopy = () => {
    navigator.clipboard.writeText(item.voice_id).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="neu-card-flat p-4">
      <div className="flex items-start justify-between mb-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-text truncate">{item.name || item.voice_id}</p>
          <span className={`inline-flex text-xs px-2 py-0.5 rounded-full text-white bg-gradient-to-r mt-1 ${isCloned ? 'from-amber-500 to-orange-400' : 'from-purple-500 to-pink-400'}`}>
            {isCloned ? '克隆' : '设计'}
          </span>
        </div>
        <span className="text-xs text-text-muted">{fmtDate(item.created_at)}</span>
      </div>

      {item.description && (
        <p className="text-xs text-text-light mt-1 line-clamp-2">{item.description}</p>
      )}

      <div className="flex items-center gap-2 mt-3 text-xs text-text-muted">
        <code className="px-1.5 py-0.5 rounded" style={{ boxShadow: 'var(--shadow-neu-inset)', background: 'var(--color-surface)' }}>
          {item.voice_id}
        </code>
      </div>

      <div className="flex gap-2 mt-3">
        <button onClick={handleCopy} className="neu-btn text-xs py-1.5 px-3 gap-1">
          <Copy size={12} /> {copied ? '已复制' : '复制 ID'}
        </button>
        <Link to={`/speech?voice_id=${item.voice_id}`} className="neu-btn text-xs py-1.5 px-3 gap-1">
          <ExternalLink size={12} /> 去语音合成
        </Link>
      </div>
    </div>
  )
}

// ─── Generation Card (for voice tab from generations) ─────────
function VoiceGenCard({ item }) {
  const play = usePlayerStore((s) => s.play)

  return (
    <div className="neu-card-flat p-4">
      <div className="flex items-start justify-between mb-2">
        <p className="text-sm font-medium text-text truncate flex-1">{item.title || TYPE_LABELS[item.service_type]}</p>
        <span className={`inline-flex text-xs px-2 py-0.5 rounded-full text-white bg-gradient-to-r ${TYPE_COLORS[item.service_type]}`}>
          {TYPE_LABELS[item.service_type]}
        </span>
      </div>
      {item.voice_id && (
        <div className="text-xs text-text-muted mt-1">
          <code className="px-1.5 py-0.5 rounded" style={{ boxShadow: 'var(--shadow-neu-inset)', background: 'var(--color-surface)' }}>
            {item.voice_id}
          </code>
        </div>
      )}
      <div className="flex items-center gap-2 mt-3">
        <span className="text-xs text-text-muted flex items-center gap-1">
          <Coins size={12} /> {item.credits_cost}
        </span>
        <span className="text-xs text-text-muted">{fmtDate(item.created_at)}</span>
        {item.result_url && (
          <button
            onClick={() => play(item.result_url, item.title || '试听')}
            className="neu-btn text-xs py-1.5 px-3 gap-1 ml-auto"
          >
            <Play size={12} /> 试听
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Pagination ───────────────────────────────────────────────
function Pagination({ page, total, pageSize, onChange }) {
  const totalPages = Math.ceil(total / pageSize) || 1
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-center gap-3 mt-6">
      <button onClick={() => onChange(page - 1)} disabled={page <= 1} className="neu-btn p-2">
        <ChevronLeft size={16} />
      </button>
      <span className="text-sm text-text-muted">
        {page} / {totalPages}
      </span>
      <button onClick={() => onChange(page + 1)} disabled={page >= totalPages} className="neu-btn p-2">
        <ChevronRight size={16} />
      </button>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────
export default function MyAssets() {
  const [tab, setTab] = useState('all')
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)

  // Voice tab — separate data source
  const [voices, setVoices] = useState([])

  const PAGE_SIZE = 20

  // Load stats once
  useEffect(() => {
    api.get('/assets/stats').then(({ data }) => setStats(data)).catch(() => {})
  }, [])

  // Reset page on tab change
  useEffect(() => { setPage(1) }, [tab])

  // Load data
  useEffect(() => {
    setLoading(true)
    if (tab === 'voice') {
      // Load both voices table AND generation records for voice tab
      Promise.all([
        api.get(`/assets/voices?page=${page}&page_size=${PAGE_SIZE}`),
        api.get(`/assets/generations?page=1&page_size=100&category=voice`),
      ]).then(([voiceRes, genRes]) => {
        setVoices(voiceRes.data.items || [])
        setItems(genRes.data.items || [])
        setTotal(genRes.data.total || 0)
      }).catch(() => {}).finally(() => setLoading(false))
    } else {
      const params = tab === 'all' ? '' : `&category=${tab}`
      api.get(`/assets/generations?page=${page}&page_size=${PAGE_SIZE}${params}`)
        .then(({ data }) => { setItems(data.items || []); setTotal(data.total || 0) })
        .catch(() => {})
        .finally(() => setLoading(false))
    }
  }, [tab, page])

  const isAudioType = (t) => ['music', 'music_cover', 'speech_sync', 'speech_async'].includes(t)

  return (
    <div className="max-w-5xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-text flex items-center gap-2">
          <FolderOpen size={24} strokeWidth={1.5} className="text-primary" /> 我的作品
        </h1>
        {stats && (
          <div className="flex gap-3">
            <span className="neu-badge">
              共 {stats.total_generations} 件作品
            </span>
            <span className="neu-badge">
              <Coins size={12} /> 累计消耗 {stats.total_credits_spent} 积分
            </span>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`neu-btn gap-1.5 text-sm ${tab === key ? 'shadow-neu-inset text-primary font-semibold' : ''}`}
          >
            <Icon size={16} strokeWidth={1.5} />
            {label}
            {stats && key !== 'all' && (
              <span className="text-xs text-text-muted ml-0.5">
                {key === 'music' ? stats.music_count : key === 'speech' ? stats.speech_count : key === 'lyrics' ? stats.lyrics_count : stats.voice_count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="text-center py-12 text-text-muted text-sm">加载中...</div>
      ) : tab === 'voice' ? (
        /* Voice tab: show Voice records + Generation records */
        <>
          {voices.length > 0 && (
            <>
              <h3 className="text-sm font-semibold text-text-light mb-3">我的音色库</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                {voices.map((v) => <VoiceCard key={v.id} item={v} />)}
              </div>
            </>
          )}
          {items.length > 0 && (
            <>
              <h3 className="text-sm font-semibold text-text-light mb-3">音色创建记录</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {items.map((g) => <VoiceGenCard key={g.id} item={g} />)}
              </div>
            </>
          )}
          {voices.length === 0 && items.length === 0 && (
            <EmptyState tab="voice" />
          )}
        </>
      ) : items.length === 0 ? (
        <EmptyState tab={tab} />
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {items.map((item) =>
              item.service_type === 'lyrics'
                ? <LyricsCard key={item.id} item={item} />
                : isAudioType(item.service_type)
                  ? <AudioCard key={item.id} item={item} />
                  : <VoiceGenCard key={item.id} item={item} />
            )}
          </div>
          <Pagination page={page} total={total} pageSize={PAGE_SIZE} onChange={setPage} />
        </>
      )}
    </div>
  )
}

function EmptyState({ tab }) {
  const hint = EMPTY_HINTS[tab] || EMPTY_HINTS.all
  return (
    <div className="text-center py-16">
      <p className="text-text-muted text-sm mb-3">{hint.text}</p>
      <Link to={hint.link} className="neu-btn neu-btn-primary text-sm py-2 px-4 inline-flex gap-1.5">
        {hint.linkText}
      </Link>
    </div>
  )
}
