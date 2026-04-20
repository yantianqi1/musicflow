import { useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  AudioWaveform,
  Mic,
  Sparkles,
  Zap,
  Coins,
  Shield,
  LogOut,
  X,
  ClipboardList,
  Gift,
} from 'lucide-react'
import useAuthStore from '../../store/authStore'

const moreItems = [
  { to: '/music/cover', icon: AudioWaveform, label: '翻唱', desc: '上传参考音频生成翻唱' },
  { to: '/speech', icon: Mic, label: '语音合成', desc: '文本转语音' },
  { to: '/voice', icon: Sparkles, label: '声音工作室', desc: '声音克隆与设计' },
  { to: '/workflow', icon: Zap, label: '一键工作流', desc: '歌词+编曲一步到位' },
  { to: '/billing', icon: Coins, label: '积分中心', desc: '充值与余额' },
  { to: '/billing/history', icon: ClipboardList, label: '消费记录', desc: '查看历史账单' },
]

export default function MoreSheet({ open, onClose }) {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const handler = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  if (!open) return null

  const handleLogout = () => {
    logout()
    onClose()
    navigate('/login')
  }

  const onLinkClick = () => onClose()

  return (
    <div className="lg:hidden" role="dialog" aria-modal="true">
      <div className="mobile-sheet-backdrop" onClick={onClose} />

      <div className="mobile-sheet-panel">
        {/* Grab handle */}
        <div className="flex justify-center pt-2.5 pb-1">
          <div className="w-10 h-1 rounded-full bg-[rgba(0,0,0,0.15)]" />
        </div>

        <div className="flex items-center justify-between px-5 pt-2 pb-3">
          <div className="min-w-0">
            <div className="text-base font-semibold truncate" style={{ color: '#1e293b' }}>
              {user?.username || '未登录'}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="neu-badge !text-xs gap-1">
                <Coins size={12} /> {user?.credits ?? 0}
              </span>
              <span
                className="neu-badge !text-xs gap-1"
                style={{ color: 'var(--color-success)' }}
              >
                <Gift size={12} /> {user?.free_credits ?? 0}
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="w-10 h-10 rounded-full flex items-center justify-center"
            style={{ background: 'var(--color-surface)', boxShadow: 'var(--shadow-neu-sm)' }}
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </div>

        <div className="h-px mx-5 bg-[rgba(0,0,0,0.06)]" />

        <ul className="p-3 grid grid-cols-1 gap-2">
          {moreItems.map((item) => {
            const Icon = item.icon
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  onClick={onLinkClick}
                  className={({ isActive }) =>
                    `flex items-center gap-3 p-3 rounded-[16px] transition-all ${
                      isActive ? 'shadow-neu-inset' : 'shadow-neu-sm active:shadow-neu-inset'
                    }`
                  }
                  style={{ background: 'var(--color-surface)', minHeight: '56px' }}
                >
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                    style={{
                      background: 'var(--color-surface-light)',
                      boxShadow: 'var(--shadow-neu-sm)',
                      color: 'var(--color-primary)',
                    }}
                  >
                    <Icon size={18} strokeWidth={1.6} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold" style={{ color: '#1e293b' }}>
                      {item.label}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: '#64748b' }}>
                      {item.desc}
                    </div>
                  </div>
                </NavLink>
              </li>
            )
          })}

          {user?.role === 'admin' && (
            <li>
              <NavLink
                to="/admin"
                onClick={onLinkClick}
                className="flex items-center gap-3 p-3 rounded-[16px] shadow-neu-sm active:shadow-neu-inset"
                style={{ background: 'var(--color-surface)', minHeight: '56px' }}
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 text-white"
                  style={{
                    background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))',
                  }}
                >
                  <Shield size={18} strokeWidth={1.6} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold" style={{ color: '#1e293b' }}>
                    管理后台
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: '#64748b' }}>
                    仅管理员可见
                  </div>
                </div>
              </NavLink>
            </li>
          )}
        </ul>

        <div className="px-3 pb-4">
          <button
            type="button"
            onClick={handleLogout}
            className="neu-btn w-full justify-center gap-2"
            style={{ minHeight: '48px' }}
          >
            <LogOut size={16} />
            退出登录
          </button>
        </div>
      </div>
    </div>
  )
}
