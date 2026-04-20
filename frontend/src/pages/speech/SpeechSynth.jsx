import { useState, useEffect } from 'react'
import { Mic } from 'lucide-react'
import api from '../../api/client'
import useAuthStore from '../../store/authStore'
import AudioPlayer from '../../components/AudioPlayer'
import ModelSelector from '../../components/ModelSelector'
import LoadingState from '../../components/LoadingState'

const MODELS = [
  { id: 'speech-2.8-hd', name: '2.8 HD' },
  { id: 'speech-2.8-turbo', name: '2.8 Turbo' },
  { id: 'speech-2.6-hd', name: '2.6 HD' },
  { id: 'speech-2.6-turbo', name: '2.6 Turbo' },
]
// 每万字符积分价格，用于显示费率
const RATE_PER_10K = { 'speech-2.8-hd': 490, 'speech-2.8-turbo': 280, 'speech-2.6-hd': 490, 'speech-2.6-turbo': 280 }
const EMOTIONS = ['auto', 'happy', 'sad', 'angry', 'fearful', 'disgusted', 'surprised', 'calm', 'fluent', 'whisper']
const EMOTION_LABELS = { auto: '自动', happy: '开心', sad: '悲伤', angry: '愤怒', fearful: '害怕', disgusted: '厌恶', surprised: '惊讶', calm: '平静', fluent: '生动', whisper: '低语' }

export default function SpeechSynth() {
  const [model, setModel] = useState('speech-2.8-hd')
  const [text, setText] = useState('')
  const [voiceId, setVoiceId] = useState('male-qn-qingse')
  const [speed, setSpeed] = useState(1.0)
  const [pitch, setPitch] = useState(0)
  const [emotion, setEmotion] = useState('auto')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [voices, setVoices] = useState([])
  const updateCredits = useAuthStore((s) => s.updateCredits)

  useEffect(() => {
    api.get('/voice/list?voice_type=system').then(({ data }) => setVoices(data.voices || [])).catch(() => {})
  }, [])

  // 动态计算预估积分
  const estimatedCost = Math.max(1, Math.ceil(RATE_PER_10K[model] * text.length / 10000))

  const generate = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const { data } = await api.post('/speech/sync', {
        model, text,
        voice_setting: { voice_id: voiceId, speed, pitch, emotion },
      })
      setResult(data)
      const balance = await api.get('/billing/balance')
      updateCredits(balance.data.credits)
    } catch (e) { setError(e.response?.data?.detail || '合成失败') }
    finally { setLoading(false) }
  }

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Mic size={24} strokeWidth={1.5} className="text-primary" /> 语音合成
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Text input */}
        <div className="lg:col-span-2 neu-card-flat p-5 flex flex-col gap-4">
          <label className="text-xs font-medium text-text-light">输入文本</label>
          <textarea value={text} onChange={(e) => setText(e.target.value)} className="neu-textarea flex-1" style={{ minHeight: '300px' }} placeholder="输入需要合成语音的文本..." />
          <p className="text-xs text-text-muted text-right">{text.length} / 10000 字符</p>
        </div>

        {/* Settings */}
        <div className="flex flex-col gap-4">
          <div className="neu-card-flat p-5 flex flex-col gap-4">
            <ModelSelector models={MODELS} value={model} onChange={setModel} prices={Object.fromEntries(Object.entries(RATE_PER_10K).map(([k,v]) => [k, `${v}/万字`]))} />

            <div>
              <label className="text-xs font-medium text-text-light mb-1.5 block">音色</label>
              <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} className="neu-select">
                {voices.length > 0
                  ? voices.map((v) => <option key={v.voice_id} value={v.voice_id}>{v.voice_name || v.voice_id}</option>)
                  : <option value="male-qn-qingse">male-qn-qingse</option>
                }
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-text-light mb-1.5 block">语速: {speed.toFixed(1)}x</label>
              <input type="range" min="0.5" max="2" step="0.1" value={speed} onChange={(e) => setSpeed(+e.target.value)} className="neu-slider" />
            </div>

            <div>
              <label className="text-xs font-medium text-text-light mb-1.5 block">语调: {pitch > 0 ? `+${pitch}` : pitch}</label>
              <input type="range" min="-12" max="12" step="1" value={pitch} onChange={(e) => setPitch(+e.target.value)} className="neu-slider" />
            </div>

            <div>
              <label className="text-xs font-medium text-text-light mb-1.5 block">情绪</label>
              <div className="flex flex-wrap gap-1">
                {EMOTIONS.map((e) => (
                  <button key={e} onClick={() => setEmotion(e)} className={`tag-btn ${emotion === e ? 'shadow-neu-inset text-primary font-semibold' : ''}`}>
                    {EMOTION_LABELS[e]}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {error && <p className="text-xs text-danger text-center">{error}</p>}

          <button onClick={generate} disabled={loading || !text} className="neu-btn neu-btn-primary py-3 w-full">
            {loading ? '合成中...' : `合成语音 (${text.length > 0 ? estimatedCost : 0} 积分)`}
          </button>

          {loading && <LoadingState text="正在合成语音..." />}
          {result && <AudioPlayer src={result.audio_url} title="语音合成结果" />}
        </div>
      </div>
    </div>
  )
}
