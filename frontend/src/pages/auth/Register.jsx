import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Music, Mail, Lock, User } from 'lucide-react'
import useAuthStore from '../../store/authStore'

export default function Register() {
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register(email, username, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || '注册失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="neu-card p-8 w-full max-w-md animate-fade-in">
        <div className="text-center mb-8">
          <div className="inline-flex p-4 rounded-full shadow-neu mb-4">
            <Music size={32} className="text-primary" strokeWidth={1.5} />
          </div>
          <h1 className="text-2xl font-bold text-text">创建账号</h1>
          <p className="text-sm text-text-muted mt-1">加入 MusicFlow 开始创作</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-xs font-medium text-text-light mb-1.5 block">用户名</label>
            <div className="relative">
              <User size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} className="neu-input pl-10" placeholder="你的昵称" required />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-text-light mb-1.5 block">邮箱</label>
            <div className="relative">
              <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="neu-input pl-10" placeholder="your@email.com" required />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-text-light mb-1.5 block">密码</label>
            <div className="relative">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="neu-input pl-10" placeholder="设置密码" required minLength={6} />
            </div>
          </div>

          {error && <p className="text-xs text-danger text-center">{error}</p>}

          <button type="submit" disabled={loading} className="neu-btn neu-btn-primary py-3 mt-2">
            {loading ? '注册中...' : '注册'}
          </button>
        </form>

        <p className="text-center text-sm text-text-muted mt-6">
          已有账号？ <Link to="/login" className="text-primary font-medium">去登录</Link>
        </p>
      </div>
    </div>
  )
}
