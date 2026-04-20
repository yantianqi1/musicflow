import { NavLink } from 'react-router-dom'
import { LayoutDashboard, FolderOpen, Music, Sparkles, Menu } from 'lucide-react'

const tabs = [
  { to: '/', icon: LayoutDashboard, label: '工作台', end: true },
  { to: '/assets', icon: FolderOpen, label: '作品' },
  { to: '/agent', icon: Sparkles, label: 'Lyra', center: true },
  { to: '/music/create', icon: Music, label: '创作' },
  { to: '__more__', icon: Menu, label: '更多', action: 'more' },
]

export default function BottomTabBar({ onOpenMore }) {
  return (
    <nav
      className="lg:hidden fixed bottom-0 left-0 right-0 z-40 safe-bottom"
      style={{
        background: 'rgba(238, 241, 245, 0.92)',
        backdropFilter: 'blur(14px)',
        WebkitBackdropFilter: 'blur(14px)',
        borderTop: '1px solid rgba(0, 0, 0, 0.05)',
      }}
    >
      <ul className="flex items-stretch justify-around h-16 px-1.5 pt-1.5">
        {tabs.map((tab) => {
          const Icon = tab.icon
          if (tab.action === 'more') {
            return (
              <li key="more" className="flex-1">
                <button
                  type="button"
                  onClick={onOpenMore}
                  className="w-full h-full flex flex-col items-center justify-center gap-0.5 text-[10.5px] font-medium transition-colors"
                  style={{ color: 'var(--color-text-light)', minHeight: '44px' }}
                  aria-label="更多"
                >
                  <Icon size={20} strokeWidth={1.7} />
                  <span>{tab.label}</span>
                </button>
              </li>
            )
          }

          if (tab.center) {
            // Elevated center tab (Lyra AI)
            return (
              <li key={tab.to} className="flex-1 flex justify-center">
                <NavLink
                  to={tab.to}
                  end={tab.end}
                  className={({ isActive }) =>
                    `relative flex flex-col items-center justify-end gap-0.5 text-[10.5px] font-semibold transition-all ${
                      isActive ? 'text-primary' : 'text-text-light'
                    }`
                  }
                  aria-label="Lyra AI"
                >
                  {({ isActive }) => (
                    <>
                      <div
                        className="w-12 h-12 rounded-2xl flex items-center justify-center -mt-4 mb-0.5 transition-all"
                        style={{
                          background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))',
                          boxShadow: isActive
                            ? '0 6px 18px rgba(99, 102, 241, 0.45), inset 0 -2px 4px rgba(0, 0, 0, 0.15)'
                            : '0 4px 14px rgba(99, 102, 241, 0.35)',
                          transform: isActive ? 'translateY(1px)' : 'translateY(0)',
                        }}
                      >
                        <Icon size={22} strokeWidth={2} className="text-white" />
                        <span className="absolute -top-3 right-[calc(50%-18px)] w-2 h-2 rounded-full bg-white/90 animate-pulse" />
                      </div>
                      <span>{tab.label}</span>
                    </>
                  )}
                </NavLink>
              </li>
            )
          }

          return (
            <li key={tab.to} className="flex-1">
              <NavLink
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  `w-full h-full flex flex-col items-center justify-center gap-0.5 text-[10.5px] font-medium transition-colors rounded-xl ${
                    isActive ? 'text-primary' : 'text-text-light'
                  }`
                }
                style={{ minHeight: '44px' }}
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      size={20}
                      strokeWidth={isActive ? 2.2 : 1.7}
                      style={isActive ? { filter: 'drop-shadow(0 2px 4px rgba(99,102,241,0.3))' } : undefined}
                    />
                    <span>{tab.label}</span>
                  </>
                )}
              </NavLink>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
