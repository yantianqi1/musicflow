export default function LoadingState({ text = '生成中...' }) {
  return (
    <div className="neu-card-flat p-8 text-center animate-fade-in">
      <div className="flex justify-center gap-1 mb-3">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="w-1.5 rounded-full bg-primary"
            style={{
              animation: 'bounce 1s infinite',
              animationDelay: `${i * 0.1}s`,
              height: '24px',
            }}
          />
        ))}
      </div>
      <p className="text-sm text-text-muted animate-pulse-soft">{text}</p>
      <style>{`
        @keyframes bounce {
          0%, 100% { transform: scaleY(0.4); opacity: 0.4; }
          50% { transform: scaleY(1); opacity: 1; }
        }
      `}</style>
    </div>
  )
}
