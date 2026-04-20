import { useState, useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Music, Mic, AudioWaveform, Sparkles, Zap, Coins, LayoutDashboard, Shield, LogOut, Gift, FolderOpen, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import useAuthStore from '../store/authStore'
import GlobalPlayer from './GlobalPlayer'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '工作台' },
  { to: '/assets', icon: FolderOpen, label: '我的作品' },
  { to: '/music/create', icon: Music, label: '音乐创作' },
  { to: '/music/cover', icon: AudioWaveform, label: '翻唱' },
  { to: '/speech', icon: Mic, label: '语音合成' },
  { to: '/voice', icon: Sparkles, label: '声音工作室' },
  { to: '/workflow', icon: Zap, label: '一键工作流' },
  { to: '/billing', icon: Coins, label: '积分中心' },
]

const COLLAPSE_STORAGE_KEY = 'musicflow.sidebar.collapsed'

const SHORTCUT_HINT = typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/i.test(navigator.userAgent || '')
  ? '⌘B'
  : 'Ctrl+B'

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === '1'
  })

  useEffect(() => {
    window.localStorage.setItem(COLLAPSE_STORAGE_KEY, collapsed ? '1' : '0')
  }, [collapsed])

  useEffect(() => {
    const handleKeydown = (e) => {
      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'b') {
        e.preventDefault()
        setCollapsed((v) => !v)
      }
    }
    window.addEventListener('keydown', handleKeydown)
    return () => window.removeEventListener('keydown', handleKeydown)
  }, [])

  const handleLogout = () => { logout(); navigate('/login') }
  const toggleCollapsed = () => setCollapsed((v) => !v)

  const navLinkClass = ({ isActive }) =>
    `flex items-center ${collapsed ? 'justify-center px-2' : 'gap-3 px-3'} py-2.5 rounded-[12px] text-sm font-medium transition-all duration-180 ${
      isActive
        ? 'shadow-neu-inset text-primary bg-surface'
        : 'hover:shadow-neu-sm hover:-translate-y-0.5 text-text-light'
    }`

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside
        className={`${collapsed ? 'w-16 p-2' : 'w-64 p-4'} flex flex-col gap-2 bg-surface shadow-neu sticky top-0 h-screen transition-all duration-200`}
        style={{ borderRadius: '0 24px 24px 0' }}
      >
        {/* Brand + collapse toggle */}
        {collapsed ? (
          <div className="flex flex-col items-center gap-1.5 pt-3 pb-2 mb-1">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center text-white font-bold text-base shadow-neu-sm"
              style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))' }}
              title="MusicFlow · 全链路音乐创作平台"
            >
              M
            </div>
            <button
              onClick={toggleCollapsed}
              title={`展开侧边栏 (${SHORTCUT_HINT})`}
              aria-label="展开侧边栏"
              className="w-8 h-8 rounded-lg inline-flex items-center justify-center text-text-muted hover:text-primary hover:shadow-neu-sm active:shadow-neu-inset transition-all duration-150"
            >
              <PanelLeftOpen size={15} strokeWidth={1.6} />
            </button>
          </div>
        ) : (
          <div className="px-3 pt-4 pb-3 mb-1 flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h1 className="text-xl font-bold bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent">
                MusicFlow
              </h1>
              <p className="text-xs text-text-muted mt-1">全链路音乐创作平台</p>
            </div>
            <button
              onClick={toggleCollapsed}
              title={`折叠侧边栏 (${SHORTCUT_HINT})`}
              aria-label="折叠侧边栏"
              className="w-8 h-8 rounded-lg inline-flex items-center justify-center text-text-muted hover:text-primary hover:shadow-neu-sm active:shadow-neu-inset transition-all duration-150 flex-shrink-0"
            >
              <PanelLeftClose size={15} strokeWidth={1.6} />
            </button>
          </div>
        )}

        <nav className="flex flex-col gap-1 flex-1">
          {/* Lyra · 主体入口 */}
          {collapsed ? (
            <NavLink
              to="/agent"
              title="Lyra · AI 音乐创作伙伴"
              aria-label="Lyra · AI 音乐创作伙伴"
              className={({ isActive }) =>
                `relative w-11 h-11 rounded-xl flex items-center justify-center mx-auto mb-1 transition-all duration-200 ${
                  isActive ? 'shadow-neu-inset' : 'shadow-neu-sm hover:-translate-y-0.5 hover:shadow-neu'
                }`
              }
              style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))' }}
            >
              <Sparkles size={18} className="text-white" strokeWidth={2} />
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-white animate-pulse" />
            </NavLink>
          ) : (
            <NavLink
              to="/agent"
              className={({ isActive }) =>
                `group relative overflow-hidden rounded-[18px] p-3.5 mb-1 transition-all duration-200 ${
                  isActive
                    ? 'shadow-neu-inset ring-1 ring-white/40'
                    : 'shadow-neu-sm hover:-translate-y-0.5 hover:shadow-neu'
                }`
              }
              style={{ background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))' }}
            >
              <div className="absolute -top-4 -right-4 w-16 h-16 bg-white/10 rounded-full blur-2xl pointer-events-none" aria-hidden />
              <div className="absolute -bottom-3 -left-3 w-12 h-12 bg-white/10 rounded-full blur-xl pointer-events-none" aria-hidden />
              <div className="relative flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center flex-shrink-0 ring-1 ring-white/30">
                  <Sparkles size={18} className="text-white" strokeWidth={2} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white text-[15px] leading-tight tracking-wide">Lyra</span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded-md bg-white/25 text-white font-semibold tracking-wider">AI</span>
                  </div>
                  <div className="text-[11px] text-white/85 mt-0.5 truncate">你的音乐创作伙伴</div>
                </div>
              </div>
            </NavLink>
          )}

          {/* 分隔 */}
          <div className={`h-px ${collapsed ? 'mx-1 my-1.5' : 'mx-2 my-2'} bg-gradient-to-r from-transparent via-[rgba(0,0,0,0.08)] to-transparent`} />

          {navItems.map((item) => {
            const ItemIcon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                title={collapsed ? item.label : undefined}
                className={navLinkClass}
              >
                <ItemIcon size={18} strokeWidth={1.5} />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            )
          })}

          {user?.role === 'admin' && (
            <NavLink
              to="/admin"
              title={collapsed ? '管理后台' : undefined}
              className={({ isActive }) =>
                `${navLinkClass({ isActive })} mt-2`
              }
            >
              <Shield size={18} strokeWidth={1.5} />
              {!collapsed && <span>管理后台</span>}
            </NavLink>
          )}
        </nav>

        {/* User info */}
        {collapsed ? (
          <div className="mt-auto flex flex-col items-center gap-1.5 pb-1">
            <span className="neu-badge gap-1 px-2" title={`积分 ${user?.credits ?? 0}`}>
              <Coins size={12} />
              <span className="text-[11px]">{user?.credits ?? 0}</span>
            </span>
            <span
              className="neu-badge gap-1 px-2"
              style={{ color: 'var(--color-success)' }}
              title={`签到 ${user?.free_credits ?? 0}`}
            >
              <Gift size={12} />
              <span className="text-[11px]">{user?.free_credits ?? 0}</span>
            </span>
            <button
              onClick={handleLogout}
              title={`退出登录（${user?.username ?? ''}）`}
              className="neu-btn w-10 h-10 p-0 justify-center"
            >
              <LogOut size={14} />
            </button>
          </div>
        ) : (
          <div className="neu-card-flat p-3 mt-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium truncate">{user?.username}</span>
            </div>
            <div className="flex gap-1.5 mb-2">
              <span className="neu-badge flex-1 justify-center">
                <Coins size={12} /> {user?.credits ?? 0}
              </span>
              <span className="neu-badge flex-1 justify-center" style={{ color: 'var(--color-success)' }}>
                <Gift size={12} /> {user?.free_credits ?? 0}
              </span>
            </div>
            <button onClick={handleLogout} className="neu-btn w-full text-xs gap-1.5 py-1.5">
              <LogOut size={14} /> 退出登录
            </button>
          </div>
        )}
      </aside>

      {/* Main */}
      <main className="flex-1 p-6 overflow-auto pb-24">
        <Outlet />
      </main>

      {/* Global audio player */}
      <GlobalPlayer />
    </div>
  )
}
