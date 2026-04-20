import { useState } from 'react'
import { Music, Wand2 } from 'lucide-react'
import api from '../../api/client'
import useAuthStore from '../../store/authStore'
import AudioPlayer from '../../components/AudioPlayer'
import ModelSelector from '../../components/ModelSelector'
import LoadingState from '../../components/LoadingState'

const MODELS = [
  { id: 'music-2.6', name: 'Music 2.6' },
  { id: 'music-2.6-free', name: 'Music 2.6 Free' },
]
const PRICES = { 'music-2.6': 140, 'music-2.6-free': 14 }
const TAGS = ['[Verse]', '[Chorus]', '[Pre Chorus]', '[Bridge]', '[Intro]', '[Outro]', '[Interlude]', '[Hook]', '[Solo]', '[Inst]']

export default function MusicCreate() {
  const [model, setModel] = useState('music-2.6')
  const [prompt, setPrompt] = useState('')
  const [lyrics, setLyrics] = useState('')
  const [isInstrumental, setIsInstrumental] = useState(false)
  const [loading, setLoading] = useState(false)
  const [lyricsLoading, setLyricsLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const updateCredits = useAuthStore((s) => s.updateCredits)

  const generateLyrics = async () => {
    if (!prompt) return
    setLyricsLoading(true)
    setError('')
    try {
      const { data } = await api.post('/music/lyrics', { prompt, mode: 'write_full_song' })
      setLyrics(data.lyrics)
      if (data.style_tags && !prompt) setPrompt(data.style_tags)
      const balance = await api.get('/billing/balance')
      updateCredits(balance.data.credits)
    } catch (e) {
      setError(e.response?.data?.detail || '歌词生成失败')
    } finally {
      setLyricsLoading(false)
    }
  }

  const generate = async () => {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const { data } = await api.post('/music/generate', {
        model, prompt, lyrics: isInstrumental ? undefined : lyrics,
        is_instrumental: isInstrumental,
      })
      setResult(data)
      const balance = await api.get('/billing/balance')
      updateCredits(balance.data.credits)
    } catch (e) {
      setError(e.response?.data?.detail || '生成失败')
    } finally {
      setLoading(false)
    }
  }

  const insertTag = (tag) => setLyrics((l) => l + (l && !l.endsWith('\n') ? '\n' : '') + tag + '\n')

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Music size={24} strokeWidth={1.5} className="text-primary" /> 音乐创作
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Lyrics */}
        <div className="neu-card-flat p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">歌词</h2>
            <button onClick={generateLyrics} disabled={lyricsLoading || !prompt} className="neu-btn text-xs gap-1">
              <Wand2 size={14} /> {lyricsLoading ? 'AI 写词中...' : 'AI 写词'}
            </button>
          </div>
          <div className="flex flex-wrap gap-1">
            {TAGS.map((t) => <button key={t} onClick={() => insertTag(t)} className="tag-btn">{t}</button>)}
          </div>
          <textarea
            value={lyrics} onChange={(e) => setLyrics(e.target.value)}
            className="neu-textarea flex-1" style={{ minHeight: '280px' }}
            placeholder="在此输入歌词，使用结构标签组织段落..."
            disabled={isInstrumental}
          />
        </div>

        {/* Right: Config */}
        <div className="flex flex-col gap-4">
          <div className="neu-card-flat p-5 flex flex-col gap-4">
            <ModelSelector models={MODELS} value={model} onChange={setModel} prices={PRICES} />

            <div>
              <label className="text-xs font-medium text-text-light mb-1.5 block">音乐描述 (Prompt)</label>
              <textarea
                value={prompt} onChange={(e) => setPrompt(e.target.value)}
                className="neu-textarea" style={{ minHeight: '80px' }}
                placeholder="描述风格、情绪、场景，如：独立民谣, 忧郁, 咖啡馆"
              />
            </div>

            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <div className={`w-10 h-5 rounded-full relative transition-colors duration-200 ${isInstrumental ? 'bg-primary' : ''}`}
                style={{ boxShadow: 'var(--shadow-neu-inset)' }}
                onClick={() => setIsInstrumental(!isInstrumental)}>
                <div className={`w-4 h-4 rounded-full bg-white shadow-neu-sm absolute top-0.5 transition-all duration-200 ${isInstrumental ? 'left-5' : 'left-0.5'}`} />
              </div>
              纯音乐（无人声）
            </label>
          </div>

          {error && <p className="text-xs text-danger text-center">{error}</p>}

          <button onClick={generate} disabled={loading || (!prompt && !lyrics)} className="neu-btn neu-btn-primary py-3 w-full">
            {loading ? '生成中...' : `生成音乐 (${PRICES[model]} 积分)`}
          </button>

          {loading && <LoadingState text="正在创作音乐..." />}
          {result && <AudioPlayer src={result.audio_url} title="生成结果" />}
        </div>
      </div>
    </div>
  )
}
