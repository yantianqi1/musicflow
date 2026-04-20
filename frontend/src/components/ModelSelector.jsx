import { Coins } from 'lucide-react'

export default function ModelSelector({ models, value, onChange, prices = {} }) {
  return (
    <div>
      <label className="text-xs font-medium text-text-light mb-1.5 block">选择模型</label>
      <div className="flex gap-2 flex-wrap">
        {models.map(({ id, name }) => (
          <button
            key={id}
            onClick={() => onChange(id)}
            className={`tag-btn flex items-center gap-1.5 px-3 py-1.5 text-xs ${
              value === id ? 'shadow-neu-inset text-primary font-semibold' : ''
            }`}
          >
            {name}
            {prices[id] != null && (
              <span className="flex items-center gap-0.5 text-text-muted">
                <Coins size={10} />{prices[id]}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
