import { useState } from 'react'
import { Zap, Music } from 'lucide-react'
import api from '../../api/client'
import useAuthStore from '../../store/authStore'
import AudioPlayer from '../../components/AudioPlayer'
import LoadingState from '../../components/LoadingState'

export default function Workflow() {
  const [theme, setTheme] = useState('')
  const [styleHint, setStyleHint] = useState('')
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const updateCredits = useAuthStore((s) => s.updateCredits)

  const run = async () => {
    setLoading(true); setError(''); setResult(null); setStep(1)
    try {
      setStep(1) // 歌词生成中
      const { data } = await api.post('/workflow/lyrics-to-song', { theme, style_hint: styleHint })
      setResult(data)
      setStep(3)
      const balance = await api.get('/billing/balance')
      updateCredits(balance.data.credits)
    } catch (e) {
      setError(e.response?.data?.detail || '工作流执行失败')
      setStep(0)
    } finally { setLoading(false) }
  }

  const steps = ['输入主题', '生成歌词', '编曲生成', '完成']

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      <h1 className="text-xl lg:text-2xl font-bold mb-5 lg:mb-6 flex items-center gap-2">
        <Zap size={22} strokeWidth={1.5} className="text-primary" /> 一键工作流
      </h1>

      {/* Progress — horizontal on desktop, compact stepper on mobile */}
      <div className="hidden lg:flex items-center gap-2 mb-6">
        {steps.map((s, i) => (
          <div key={i} className="flex items-center gap-2 flex-1">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-200 ${
              i <= step
                ? 'bg-gradient-to-br from-primary to-accent text-white'
                : 'shadow-neu-sm text-text-muted'
            }`}>{i + 1}</div>
            <span className={`text-xs ${i <= step ? 'text-primary font-medium' : 'text-text-muted'}`}>{s}</span>
            {i < steps.length - 1 && <div className={`flex-1 h-0.5 rounded ${i < step ? 'bg-primary' : 'bg-surface-dark'}`} />}
          </div>
        ))}
      </div>

      <div className="lg:hidden flex items-center justify-between gap-1 mb-5 px-1">
        {steps.map((s, i) => (
          <div key={i} className="flex flex-col items-center gap-1 flex-1">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold transition-all duration-200 ${
              i <= step
                ? 'bg-gradient-to-br from-primary to-accent text-white'
                : 'shadow-neu-sm text-text-muted'
            }`}>{i + 1}</div>
            <span className={`text-[10.5px] text-center ${i <= step ? 'text-primary font-medium' : 'text-text-muted'}`}>{s}</span>
          </div>
        ))}
      </div>

      <div className="neu-card-flat p-4 lg:p-6 flex flex-col gap-4 lg:gap-5">
        <div className="flex items-center gap-2 text-sm font-medium text-text">
          <Music size={18} /> 灵感到歌曲
        </div>
        <p className="text-xs text-text-muted">输入一个主题，AI 会自动生成歌词并编曲，产出一首完整歌曲</p>

        <div>
          <label className="text-xs font-medium text-text-light mb-1.5 block">歌曲主题</label>
          <input value={theme} onChange={(e) => setTheme(e.target.value)} className="neu-input" placeholder="如：一首关于夏日海边的轻快情歌" />
        </div>

        <div>
          <label className="text-xs font-medium text-text-light mb-1.5 block">风格提示（可选）</label>
          <input value={styleHint} onChange={(e) => setStyleHint(e.target.value)} className="neu-input" placeholder="如：流行、民谣、电子" />
        </div>

        {error && <p className="text-xs text-danger">{error}</p>}

        <button
          onClick={run}
          disabled={loading || !theme}
          className="neu-btn neu-btn-primary !py-3.5 !min-h-[52px] font-semibold"
        >
          {loading ? '执行中...' : '一键生成歌曲 (147 积分起 / 约1.47元)'}
        </button>

        {loading && <LoadingState text={step === 1 ? '正在生成歌词...' : '正在编曲...'} />}

        {result && (
          <div className="flex flex-col gap-4 animate-fade-in">
            <div className="neu-card-flat p-4">
              <h3 className="text-sm font-semibold mb-1">{result.song_title}</h3>
              <p className="text-xs text-text-muted mb-2">风格: {result.style_tags}</p>
              <pre className="text-xs text-text-light whitespace-pre-wrap max-h-48 overflow-auto p-3 rounded-[12px]" style={{ boxShadow: 'var(--shadow-neu-inset)' }}>
                {result.lyrics}
              </pre>
            </div>
            <AudioPlayer src={result.audio_url} title={result.song_title} />
          </div>
        )}
      </div>
    </div>
  )
}
