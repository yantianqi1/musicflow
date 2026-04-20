import { useState } from 'react'
import { AudioWaveform } from 'lucide-react'
import api from '../../api/client'
import useAuthStore from '../../store/authStore'
import AudioPlayer from '../../components/AudioPlayer'
import ModelSelector from '../../components/ModelSelector'
import LoadingState from '../../components/LoadingState'

const MODELS = [
  { id: 'music-cover', name: 'Music Cover' },
  { id: 'music-cover-free', name: 'Music Cover Free' },
]
const PRICES = { 'music-cover': 140, 'music-cover-free': 14 }

export default function MusicCover() {
  const [model, setModel] = useState('music-cover')
  const [prompt, setPrompt] = useState('')
  const [audioUrl, setAudioUrl] = useState('')
  const [lyrics, setLyrics] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const updateCredits = useAuthStore((s) => s.updateCredits)

  const generate = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const { data } = await api.post('/music/cover', { model, prompt, audio_url: audioUrl, lyrics: lyrics || undefined })
      setResult(data)
      const balance = await api.get('/billing/balance')
      updateCredits(balance.data.credits)
    } catch (e) { setError(e.response?.data?.detail || '翻唱生成失败') }
    finally { setLoading(false) }
  }

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <AudioWaveform size={24} strokeWidth={1.5} className="text-primary" /> 翻唱
      </h1>

      <div className="neu-card-flat p-6 flex flex-col gap-5">
        <ModelSelector models={MODELS} value={model} onChange={setModel} prices={PRICES} />

        <div>
          <label className="text-xs font-medium text-text-light mb-1.5 block">参考音频 URL</label>
          <input value={audioUrl} onChange={(e) => setAudioUrl(e.target.value)} className="neu-input" placeholder="输入参考音频的 URL 地址" />
        </div>

        <div>
          <label className="text-xs font-medium text-text-light mb-1.5 block">翻唱风格描述</label>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} className="neu-textarea" style={{ minHeight: '80px' }} placeholder="描述目标翻唱风格，如：爵士风格, 慵懒, 夜晚氛围" />
        </div>

        <div>
          <label className="text-xs font-medium text-text-light mb-1.5 block">歌词（可选，不填则自动提取）</label>
          <textarea value={lyrics} onChange={(e) => setLyrics(e.target.value)} className="neu-textarea" placeholder="可选输入歌词" />
        </div>

        {error && <p className="text-xs text-danger text-center">{error}</p>}

        <button onClick={generate} disabled={loading || !prompt || !audioUrl} className="neu-btn neu-btn-primary py-3">
          {loading ? '生成中...' : `生成翻唱 (${PRICES[model]} 积分)`}
        </button>

        {loading && <LoadingState text="正在生成翻唱..." />}
        {result && <AudioPlayer src={result.audio_url} title="翻唱结果" />}
      </div>
    </div>
  )
}
