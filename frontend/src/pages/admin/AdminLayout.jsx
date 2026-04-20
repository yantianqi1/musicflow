import { useState, useEffect } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { Users, BarChart3, Settings, Shield } from 'lucide-react'
import api from '../../api/client'

function UserManage() {
  const [users, setUsers] = useState([])
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [adjustId, setAdjustId] = useState(null)
  const [adjustAmount, setAdjustAmount] = useState('')
  const [adjustDesc, setAdjustDesc] = useState('')

  const fetchUsers = () => {
    api.get(`/admin/users?page=${page}&search=${search}`).then(({ data }) => {
      setUsers(data.items); setTotal(data.total)
    })
  }

  useEffect(fetchUsers, [page, search])

  const adjust = async (userId) => {
    await api.put(`/admin/users/${userId}/credits`, { amount: +adjustAmount, description: adjustDesc })
    setAdjustId(null); setAdjustAmount(''); setAdjustDesc(''); fetchUsers()
  }

  const toggleStatus = async (userId, active) => {
    await api.put(`/admin/users/${userId}/status`, { is_active: !active })
    fetchUsers()
  }

  return (
    <div>
      <input value={search} onChange={(e) => setSearch(e.target.value)} className="neu-input mb-4" placeholder="搜索邮箱或用户名..." />
      <div className="flex flex-col gap-2">
        {users.map((u) => (
          <div key={u.id} className="neu-card-flat p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{u.username} <span className="text-xs text-text-muted">({u.email})</span></p>
                <p className="text-xs text-text-muted">角色: {u.role} | 积分: {u.credits} | {u.is_active ? '活跃' : '已禁用'}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setAdjustId(adjustId === u.id ? null : u.id)} className="neu-btn text-xs">调整积分</button>
                <button onClick={() => toggleStatus(u.id, u.is_active)} className={`neu-btn text-xs ${u.is_active ? 'neu-btn-danger' : 'neu-btn-primary'}`}>
                  {u.is_active ? '禁用' : '启用'}
                </button>
              </div>
            </div>
            {adjustId === u.id && (
              <div className="flex gap-2 mt-3 animate-fade-in">
                <input type="number" value={adjustAmount} onChange={(e) => setAdjustAmount(e.target.value)} className="neu-input w-32" placeholder="积分数" />
                <input value={adjustDesc} onChange={(e) => setAdjustDesc(e.target.value)} className="neu-input flex-1" placeholder="备注" />
                <button onClick={() => adjust(u.id)} className="neu-btn neu-btn-primary text-xs">确认</button>
              </div>
            )}
          </div>
        ))}
      </div>
      {total > 20 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="neu-btn text-xs">上一页</button>
          <span className="text-sm text-text-muted">{page}</span>
          <button onClick={() => setPage((p) => p + 1)} disabled={page * 20 >= total} className="neu-btn text-xs">下一页</button>
        </div>
      )}
    </div>
  )
}

function Stats() {
  const [stats, setStats] = useState(null)
  useEffect(() => { api.get('/admin/stats').then(({ data }) => setStats(data)) }, [])

  if (!stats) return <p className="text-sm text-text-muted">加载中...</p>

  const cards = [
    { label: '总用户数', value: stats.total_users, color: 'from-primary to-accent' },
    { label: '活跃用户', value: stats.active_users, color: 'from-emerald-500 to-teal-400' },
    { label: '总生成次数', value: stats.total_generations, color: 'from-amber-500 to-orange-400' },
    { label: '总消耗积分', value: stats.total_credits_consumed, color: 'from-rose-500 to-pink-400' },
    { label: '总充值积分', value: stats.total_credits_recharged, color: 'from-blue-500 to-cyan-400' },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
      {cards.map(({ label, value, color }) => (
        <div key={label} className="neu-card-flat p-5 text-center">
          <p className="text-xs text-text-muted mb-1">{label}</p>
          <p className={`text-2xl font-bold bg-gradient-to-r ${color} bg-clip-text text-transparent`}>{value.toLocaleString()}</p>
        </div>
      ))}
    </div>
  )
}

function PricingConfig() {
  const [rules, setRules] = useState([])
  const [editId, setEditId] = useState(null)
  const [editCost, setEditCost] = useState('')
  const [checkinReward, setCheckinReward] = useState(10)
  const [newReward, setNewReward] = useState('')
  const [rewardSaved, setRewardSaved] = useState(false)

  const fetchRules = () => api.get('/admin/pricing').then(({ data }) => setRules(data))
  const fetchReward = () => api.get('/admin/config/checkin-reward').then(({ data }) => {
    setCheckinReward(data.daily_checkin_reward)
    setNewReward(String(data.daily_checkin_reward))
  })
  useEffect(() => { fetchRules(); fetchReward() }, [])

  const save = async (id) => {
    await api.put(`/admin/pricing/${id}`, { credits_per_use: +editCost })
    setEditId(null); fetchRules()
  }

  const saveReward = async () => {
    await api.put(`/admin/config/checkin-reward?amount=${+newReward}`)
    setCheckinReward(+newReward)
    setRewardSaved(true)
    setTimeout(() => setRewardSaved(false), 2000)
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Checkin reward config */}
      <div className="neu-card-flat p-4">
        <p className="text-sm font-semibold mb-2">每日签到奖励</p>
        <div className="flex gap-2 items-center">
          <input type="number" value={newReward} onChange={(e) => setNewReward(e.target.value)} className="neu-input w-32" />
          <span className="text-xs text-text-muted">签到积分/天</span>
          <button onClick={saveReward} className="neu-btn neu-btn-primary text-xs">保存</button>
          {rewardSaved && <span className="text-xs text-success">已保存</span>}
        </div>
        <p className="text-xs text-text-muted mt-1">当前: {checkinReward} 积分/天（签到积分仅可用于 Free 模型）</p>
      </div>

      {/* Pricing rules */}
      <div className="flex flex-col gap-2">
      {rules.map((r) => (
        <div key={r.id} className="neu-card-flat p-4 flex items-center justify-between">
          <div>
            <p className="text-sm font-medium">{r.description || r.service_type}</p>
            <p className="text-xs text-text-muted">服务: {r.service_type} {r.model ? `| 模型: ${r.model}` : ''}</p>
          </div>
          {editId === r.id ? (
            <div className="flex gap-2">
              <input type="number" value={editCost} onChange={(e) => setEditCost(e.target.value)} className="neu-input w-24" />
              <button onClick={() => save(r.id)} className="neu-btn neu-btn-primary text-xs">保存</button>
              <button onClick={() => setEditId(null)} className="neu-btn text-xs">取消</button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="neu-badge">{r.credits_per_use} 积分/次</span>
              <button onClick={() => { setEditId(r.id); setEditCost(String(r.credits_per_use)) }} className="neu-btn text-xs">修改</button>
            </div>
          )}
        </div>
      ))}
      </div>
    </div>
  )
}

const tabs = [
  { path: '', icon: Users, label: '用户管理' },
  { path: 'stats', icon: BarChart3, label: '数据统计' },
  { path: 'pricing', icon: Settings, label: '计费配置' },
]

export default function AdminLayout() {
  return (
    <div className="max-w-4xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold mb-6 flex items-center gap-2">
        <Shield size={24} strokeWidth={1.5} className="text-primary" /> 管理后台
      </h1>

      <div className="flex gap-2 mb-6">
        {tabs.map(({ path, icon: Icon, label }) => (
          <NavLink key={path} to={`/admin/${path}`} end
            className={({ isActive }) => `neu-btn gap-1.5 ${isActive ? 'shadow-neu-inset text-primary' : ''}`}>
            <Icon size={16} /> {label}
          </NavLink>
        ))}
      </div>

      <Routes>
        <Route index element={<UserManage />} />
        <Route path="stats" element={<Stats />} />
        <Route path="pricing" element={<PricingConfig />} />
      </Routes>
    </div>
  )
}
