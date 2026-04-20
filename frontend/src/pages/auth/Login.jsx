import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Music, Mail, Lock } from 'lucide-react'
import useAuthStore from '../../store/authStore'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4 safe-top safe-bottom">
      <div className="neu-card p-6 lg:p-8 w-full max-w-md animate-fade-in">
        <div className="text-center mb-6 lg:mb-8">
          <div className="inline-flex p-4 rounded-full shadow-neu mb-4">
            <Music size={32} className="text-primary" strokeWidth={1.5} />
          </div>
          <h1 className="text-2xl font-bold text-text">欢迎回来</h1>
          <p className="text-sm text-text-muted mt-1">登录 MusicFlow 创作平台</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-xs font-medium text-text-light mb-1.5 block">邮箱</label>
            <div className="relative">
              <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="neu-input !pl-10"
                placeholder="your@email.com"
                required
                autoComplete="email"
                inputMode="email"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-text-light mb-1.5 block">密码</label>
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted pointer-events-none" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="neu-input !pl-10"
                placeholder="输入密码"
                required
                autoComplete="current-password"
              />
            </div>
          </div>

          {error && <p className="text-xs text-danger text-center">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="neu-btn neu-btn-primary !py-3.5 !min-h-[52px] mt-2 font-semibold"
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>

        <p className="text-center text-sm text-text-muted mt-5 lg:mt-6">
          还没有账号？ <Link to="/register" className="text-primary font-medium">立即注册</Link>
        </p>
      </div>
    </div>
  )
}
