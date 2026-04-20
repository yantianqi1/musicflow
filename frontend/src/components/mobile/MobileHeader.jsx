import { Coins, Gift, Menu } from 'lucide-react'
import { Link } from 'react-router-dom'
import useAuthStore from '../../store/authStore'

export default function MobileHeader({ onOpenMore }) {
  const { user } = useAuthStore()
  const initial = (user?.username || 'U').trim().charAt(0).toUpperCase()

  return (
    <header
      className="lg:hidden sticky top-0 z-40 safe-top"
      style={{
        background: 'rgba(238, 241, 245, 0.88)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
      }}
    >
      <div className="flex items-center justify-between h-14 px-4">
        <Link to="/" className="flex items-center gap-2 min-w-0" aria-label="MusicFlow 首页">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-white font-bold text-base flex-shrink-0"
            style={{
              background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))',
              boxShadow: 'var(--shadow-neu-sm)',
            }}
          >
            M
          </div>
          <div className="min-w-0">
            <div className="text-[15px] font-bold leading-tight bg-gradient-to-r from-primary to-accent bg-clip-text text-transparent truncate">
              MusicFlow
            </div>
          </div>
        </Link>

        <div className="flex items-center gap-2">
          <Link
            to="/billing"
            className="flex items-center gap-1 px-2.5 h-8 rounded-full text-xs font-semibold"
            style={{
              background: 'var(--color-surface)',
              boxShadow: 'var(--shadow-neu-sm)',
              color: 'var(--color-primary)',
            }}
            aria-label={`积分 ${user?.credits ?? 0}`}
          >
            <Coins size={13} strokeWidth={2} />
            <span>{user?.credits ?? 0}</span>
          </Link>
          {typeof user?.free_credits === 'number' && (
            <Link
              to="/billing"
              className="flex items-center gap-1 px-2.5 h-8 rounded-full text-xs font-semibold"
              style={{
                background: 'var(--color-surface)',
                boxShadow: 'var(--shadow-neu-sm)',
                color: 'var(--color-success)',
              }}
              aria-label={`免费积分 ${user?.free_credits ?? 0}`}
            >
              <Gift size={13} strokeWidth={2} />
              <span>{user.free_credits}</span>
            </Link>
          )}
          <button
            type="button"
            onClick={onOpenMore}
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{
              background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))',
              boxShadow: 'var(--shadow-neu-sm)',
              color: '#fff',
            }}
            aria-label="打开更多菜单"
          >
            {user ? (
              <span className="text-sm font-bold">{initial}</span>
            ) : (
              <Menu size={18} strokeWidth={2} />
            )}
          </button>
        </div>
      </div>
    </header>
  )
}
