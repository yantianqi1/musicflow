import { useState, useEffect } from 'react'
import { Clock, ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import api from '../../api/client'

const TYPE_LABELS = { recharge: '充值', consume: '消费', admin_grant: '管理员调整', refund: '退款' }
const TYPE_COLORS = { recharge: 'text-success', consume: 'text-danger', admin_grant: 'text-primary', refund: 'text-warning' }

export default function History() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)

  useEffect(() => {
    api.get(`/billing/transactions?page=${page}&page_size=20`).then(({ data }) => {
      setItems(data.items); setTotal(data.total)
    }).catch(() => {})
  }, [page])

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/billing" className="neu-btn p-2"><ArrowLeft size={18} /></Link>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Clock size={24} strokeWidth={1.5} className="text-primary" /> 消费记录
        </h1>
      </div>

      <div className="flex flex-col gap-2">
        {items.map((tx) => (
          <div key={tx.id} className="neu-card-flat p-4 flex items-center justify-between">
            <div>
              <span className={`text-xs font-semibold ${TYPE_COLORS[tx.type] || ''}`}>{TYPE_LABELS[tx.type] || tx.type}</span>
              <p className="text-sm text-text mt-0.5">{tx.description}</p>
              <p className="text-xs text-text-muted">{new Date(tx.created_at).toLocaleString()}</p>
            </div>
            <div className="text-right">
              <p className={`text-lg font-bold ${tx.amount > 0 ? 'text-success' : 'text-danger'}`}>
                {tx.amount > 0 ? '+' : ''}{tx.amount}
              </p>
              <p className="text-xs text-text-muted">余额: {tx.balance_after}</p>
            </div>
          </div>
        ))}
        {items.length === 0 && <p className="text-center text-text-muted text-sm py-8">暂无记录</p>}
      </div>

      {total > 20 && (
        <div className="flex justify-center gap-2 mt-4">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="neu-btn text-xs">上一页</button>
          <span className="text-sm text-text-muted flex items-center">{page} / {Math.ceil(total / 20)}</span>
          <button onClick={() => setPage((p) => p + 1)} disabled={page * 20 >= total} className="neu-btn text-xs">下一页</button>
        </div>
      )}
    </div>
  )
}
