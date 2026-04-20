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
      <div className="flex items-center gap-3 mb-5 lg:mb-6">
        <Link to="/billing" className="neu-btn !w-11 !h-11 !p-0 justify-center" aria-label="返回"><ArrowLeft size={18} /></Link>
        <h1 className="text-xl lg:text-2xl font-bold flex items-center gap-2">
          <Clock size={22} strokeWidth={1.5} className="text-primary" /> 消费记录
        </h1>
      </div>

      <div className="flex flex-col gap-2">
        {items.map((tx) => (
          <div key={tx.id} className="neu-card-flat p-4 flex items-center justify-between gap-3">
            <div className="min-w-0 flex-1">
              <span className={`text-xs font-semibold ${TYPE_COLORS[tx.type] || ''}`}>{TYPE_LABELS[tx.type] || tx.type}</span>
              <p className="text-sm text-text mt-0.5 truncate">{tx.description}</p>
              <p className="text-xs text-text-muted mt-0.5">{new Date(tx.created_at).toLocaleString()}</p>
            </div>
            <div className="text-right flex-shrink-0">
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
        <div className="flex justify-center items-center gap-3 mt-5">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="neu-btn !w-11 !h-11 !p-0 justify-center"
            aria-label="上一页"
          >
            <ArrowLeft size={18} />
          </button>
          <span className="text-sm text-text-muted min-w-[60px] text-center">{page} / {Math.ceil(total / 20)}</span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page * 20 >= total}
            className="neu-btn !w-11 !h-11 !p-0 justify-center"
            aria-label="下一页"
          >
            <ArrowLeft size={18} className="rotate-180" />
          </button>
        </div>
      )}
    </div>
  )
}
