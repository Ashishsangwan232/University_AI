export function QuickAction({ icon, title, desc, onClick }: { icon: string; title: string; desc: string; onClick: () => void }) {
  return <button className="quick-action" onClick={onClick}><span className="quick-icon">{icon}</span><div><strong>{title}</strong><small>{desc}</small></div><b>→</b></button>
}
