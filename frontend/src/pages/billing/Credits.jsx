import { useState } from 'react'
import { Coins, Plus, Clock } from 'lucide-react'
import { Link } from 'react-router-dom'
import api from '../../api/client'
import useAuthStore from '../../store/authStore'

const PACKAGES = [
  { amount: 100, price: '1 元', popular: false },
  { amount: 500, price: '5 元', popular: false },
  { amount: 1000, price: '10 元', popular: true },
  { amount: 5000, price: '50 元', popular: false },
]

export default function Credits() {
  const { user, updateCredits } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState('')

  const recharge = async (amount) => {
    setLoading(true); setSuccess('')
    try {
      const { data } = await api.post('/billing/recharge', { amount })
      updateCredits(data.credits)
      setSuccess(`充值成功！当前积分: ${data.credits}`)
    } catch {} finally { setLoading(false) }
  }

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Coins size={24} strokeWidth={1.5} className="text-primary" /> 积分中心
      </h1>

      {/* Current balance */}
      <div className="neu-card-flat p-6 mb-6 text-center">
        <p className="text-xs text-text-muted mb-2">当前积分余额</p>
        <p className="text-4xl font-bold text-primary">{user?.credits ?? 0}</p>
        <p className="text-xs text-text-muted mt-2">1 积分 = 0.01 元</p>
      </div>

      {/* Recharge packages */}
      <h2 className="text-lg font-semibold mb-4">充值套餐</h2>
      <div className="grid grid-cols-2 gap-4 mb-6">
        {PACKAGES.map(({ amount, price, popular }) => (
          <button key={amount} onClick={() => recharge(amount)} disabled={loading}
            className={`neu-card neu-card-hover p-5 text-center relative ${popular ? 'ring-2 ring-primary' : ''}`}>
            {popular && <span className="absolute -top-2 left-1/2 -translate-x-1/2 bg-primary text-white text-xs px-2 py-0.5 rounded-full">推荐</span>}
            <p className="text-2xl font-bold text-primary">{amount}</p>
            <p className="text-xs text-text-muted mt-1">积分</p>
            <p className="text-sm font-medium mt-2">{price}</p>
          </button>
        ))}
      </div>

      {success && <p className="text-sm text-success text-center mb-4">{success}</p>}

      <Link to="/billing/history" className="neu-btn w-full justify-center gap-2">
        <Clock size={16} /> 查看消费记录
      </Link>
    </div>
  )
}
