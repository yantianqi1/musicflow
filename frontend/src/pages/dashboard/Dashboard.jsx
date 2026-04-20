import { useState, useEffect } from 'react'
import { Music, Mic, AudioWaveform, Sparkles, Coins, Gift, CalendarCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import api from '../../api/client'
import useAuthStore from '../../store/authStore'

const quickActions = [
  { to: '/music/create', icon: Music, label: '创作音乐', desc: '歌词 + 编曲一步到位', color: 'from-primary to-accent' },
  { to: '/music/cover', icon: AudioWaveform, label: '翻唱', desc: '上传参考音频生成翻唱', color: 'from-pink-500 to-rose-400' },
  { to: '/speech', icon: Mic, label: '语音合成', desc: '文字转语音，多情感表达', color: 'from-emerald-500 to-teal-400' },
  { to: '/voice', icon: Sparkles, label: '声音工作室', desc: '克隆或设计专属音色', color: 'from-amber-500 to-orange-400' },
]

export default function Dashboard() {
  const { user, updateCredits } = useAuthStore()
  const [checkinStatus, setCheckinStatus] = useState(null)
  const [checkinLoading, setCheckinLoading] = useState(false)
  const [checkinMsg, setCheckinMsg] = useState('')

  useEffect(() => {
    api.get('/checkin/status').then(({ data }) => setCheckinStatus(data)).catch(() => {})
  }, [])

  const handleCheckin = async () => {
    setCheckinLoading(true)
    setCheckinMsg('')
    try {
      const { data } = await api.post('/checkin/daily')
      setCheckinMsg(data.message)
      updateCredits(data.credits, data.free_credits)
      setCheckinStatus((s) => s ? { ...s, checked_in_today: true, streak: (s.streak || 0) + 1, month_count: (s.month_count || 0) + 1, free_credits: data.free_credits } : s)
    } catch (e) {
      setCheckinMsg(e.response?.data?.detail || '签到失败')
    } finally {
      setCheckinLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-text">你好，{user?.username}</h1>
        <p className="text-sm text-text-muted mt-1">开始你的音乐创作之旅</p>
      </div>

      {/* Credits + Checkin */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Credits card */}
        <div className="neu-card-flat p-6">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-text-muted">充值积分（全部模型可用）</p>
            <Link to="/billing" className="neu-btn neu-btn-primary text-xs py-1.5 px-3">充值</Link>
          </div>
          <p className="text-3xl font-bold text-primary flex items-center gap-2">
            <Coins size={28} strokeWidth={1.5} />{user?.credits ?? 0}
          </p>
          <p className="text-xs text-text-muted mt-1">1 积分 = 0.01 元</p>
        </div>

        {/* Free credits + checkin */}
        <div className="neu-card-flat p-6">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-text-muted">签到积分（仅 Free 模型可用）</p>
            <button
              onClick={handleCheckin}
              disabled={checkinLoading || checkinStatus?.checked_in_today}
              className={`neu-btn text-xs py-1.5 px-3 gap-1 ${checkinStatus?.checked_in_today ? '' : 'neu-btn-primary'}`}
            >
              <CalendarCheck size={14} />
              {checkinStatus?.checked_in_today ? '已签到' : checkinLoading ? '签到中...' : '签到'}
            </button>
          </div>
          <p className="text-3xl font-bold flex items-center gap-2" style={{ color: 'var(--color-success)' }}>
            <Gift size={28} strokeWidth={1.5} />{user?.free_credits ?? 0}
          </p>
          {checkinStatus && (
            <p className="text-xs text-text-muted mt-1">
              连续签到 {checkinStatus.streak} 天 | 本月 {checkinStatus.month_count} 次 | 每日 +{checkinStatus.daily_reward}
            </p>
          )}
          {checkinMsg && <p className="text-xs mt-2 text-success">{checkinMsg}</p>}
        </div>
      </div>

      {/* Quick actions */}
      <h2 className="text-lg font-semibold mb-4 text-text">快速开始</h2>
      <div className="grid grid-cols-2 gap-4">
        {quickActions.map(({ to, icon: Icon, label, desc, color }) => (
          <Link key={to} to={to} className="neu-card neu-card-hover p-5 block">
            <div className={`inline-flex p-3 rounded-[12px] bg-gradient-to-br ${color} mb-3`}>
              <Icon size={22} className="text-white" strokeWidth={1.5} />
            </div>
            <h3 className="font-semibold text-text text-sm">{label}</h3>
            <p className="text-xs text-text-muted mt-1">{desc}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
