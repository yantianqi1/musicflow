import { useState } from 'react'
import { Sparkles, Upload, Palette, List, Trash2 } from 'lucide-react'
import api from '../../api/client'
import useAuthStore from '../../store/authStore'
import AudioPlayer from '../../components/AudioPlayer'
import LoadingState from '../../components/LoadingState'

const TABS = [
  { id: 'clone', icon: Upload, label: '声音克隆' },
  { id: 'design', icon: Palette, label: '声音设计' },
  { id: 'manage', icon: List, label: '声音管理' },
]

export default function VoiceStudio() {
  const [tab, setTab] = useState('clone')

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      <h1 className="text-xl lg:text-2xl font-bold mb-5 lg:mb-6 flex items-center gap-2">
        <Sparkles size={22} strokeWidth={1.5} className="text-primary" /> 声音工作室
      </h1>

      <div className="scroll-chip-row mb-5 lg:flex lg:gap-2 lg:mb-6 lg:overflow-visible">
        {TABS.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`neu-btn gap-1.5 whitespace-nowrap ${tab === id ? 'shadow-neu-inset text-primary font-semibold' : ''}`}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </div>

      {tab === 'clone' && <CloneTab />}
      {tab === 'design' && <DesignTab />}
      {tab === 'manage' && <ManageTab />}
    </div>
  )
}

function CloneTab() {
  const [file, setFile] = useState(null)
  const [voiceId, setVoiceId] = useState('')
  const [text, setText] = useState('你好，这是一段克隆声音的试听文本。')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const updateCredits = useAuthStore((s) => s.updateCredits)

  const handleClone = async () => {
    if (!file || !voiceId) return
    setLoading(true); setError(''); setResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('purpose', 'voice_clone')
      const uploadRes = await api.post('/voice/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      const fileId = uploadRes.data.file_id

      const { data } = await api.post('/voice/clone', { file_id: fileId, voice_id: voiceId, text })
      setResult(data)
      const balance = await api.get('/billing/balance')
      updateCredits(balance.data.credits)
    } catch (e) { setError(e.response?.data?.detail || '克隆失败') }
    finally { setLoading(false) }
  }

  return (
    <div className="neu-card-flat p-4 lg:p-6 flex flex-col gap-4">
      <div>
        <label className="text-xs font-medium text-text-light mb-1.5 block">上传待克隆音频（10秒-5分钟）</label>
        <input type="file" accept=".mp3,.m4a,.wav" onChange={(e) => setFile(e.target.files?.[0] || null)} className="neu-input text-sm" />
      </div>
      <div>
        <label className="text-xs font-medium text-text-light mb-1.5 block">自定义 Voice ID</label>
        <input value={voiceId} onChange={(e) => setVoiceId(e.target.value)} className="neu-input" placeholder="my_custom_voice" />
      </div>
      <div>
        <label className="text-xs font-medium text-text-light mb-1.5 block">试听文本</label>
        <textarea value={text} onChange={(e) => setText(e.target.value)} className="neu-textarea" />
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      <button
        onClick={handleClone}
        disabled={loading || !file || !voiceId}
        className="neu-btn neu-btn-primary !py-3.5 !min-h-[52px] font-semibold"
      >
        {loading ? '克隆中...' : '开始克隆 (1386 积分 / 13.86元)'}
      </button>
      {loading && <LoadingState text="正在克隆声音..." />}
      {result?.trial_audio_url && <AudioPlayer src={result.trial_audio_url} title={`克隆结果: ${result.voice_id}`} />}
    </div>
  )
}

function DesignTab() {
  const [prompt, setPrompt] = useState('')
  const [previewText, setPreviewText] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const updateCredits = useAuthStore((s) => s.updateCredits)

  const handleDesign = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const { data } = await api.post('/voice/design', { prompt, preview_text: previewText })
      setResult(data)
      const balance = await api.get('/billing/balance')
      updateCredits(balance.data.credits)
    } catch (e) { setError(e.response?.data?.detail || '设计失败') }
    finally { setLoading(false) }
  }

  return (
    <div className="neu-card-flat p-4 lg:p-6 flex flex-col gap-4">
      <div>
        <label className="text-xs font-medium text-text-light mb-1.5 block">音色描述</label>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} className="neu-textarea"
          placeholder="详细描述想要的音色，如：温柔甜美的女性声音，语速适中，适合讲述浪漫爱情故事" />
      </div>
      <div>
        <label className="text-xs font-medium text-text-light mb-1.5 block">试听文本（最长500字）</label>
        <textarea value={previewText} onChange={(e) => setPreviewText(e.target.value)} className="neu-textarea"
          placeholder="输入用于试听的文本" />
      </div>
      {error && <p className="text-xs text-danger">{error}</p>}
      <button
        onClick={handleDesign}
        disabled={loading || !prompt || !previewText}
        className="neu-btn neu-btn-primary !py-3.5 !min-h-[52px] font-semibold"
      >
        {loading ? '设计中...' : '生成音色 (1386 积分 / 13.86元)'}
      </button>
      {loading && <LoadingState text="正在设计音色..." />}
      {result?.trial_audio_url && <AudioPlayer src={result.trial_audio_url} title={`新音色: ${result.voice_id}`} />}
    </div>
  )
}

function ManageTab() {
  const [voices, setVoices] = useState([])
  const [loading, setLoading] = useState(false)

  const fetchVoices = async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/voice/list?voice_type=all')
      setVoices(data.voices || [])
    } catch {} finally { setLoading(false) }
  }

  const deleteVoice = async (vid) => {
    if (!confirm(`确定删除音色 ${vid} 吗？`)) return
    try { await api.delete(`/voice/${vid}`); fetchVoices() } catch {}
  }

  return (
    <div className="neu-card-flat p-4 lg:p-6 flex flex-col gap-4">
      <button onClick={fetchVoices} className="neu-btn" disabled={loading}>
        {loading ? '加载中...' : '加载音色列表'}
      </button>
      {voices.length > 0 && (
        <div className="flex flex-col gap-2 max-h-96 overflow-auto">
          {voices.map((v) => (
            <div key={v.voice_id} className="flex items-center justify-between gap-2 p-3 rounded-[12px]" style={{ boxShadow: 'var(--shadow-neu-sm)' }}>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{v.voice_name || v.voice_id}</p>
                <p className="text-xs text-text-muted truncate">{v.voice_type} {v.description ? `- ${v.description}` : ''}</p>
              </div>
              {v.voice_type !== 'system' && (
                <button
                  onClick={() => deleteVoice(v.voice_id)}
                  className="neu-btn neu-btn-danger !w-10 !h-10 !p-0 !min-h-[40px] justify-center flex-shrink-0"
                  aria-label="删除音色"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
