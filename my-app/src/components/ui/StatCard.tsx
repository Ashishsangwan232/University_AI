export function StatCard({ label, value, note, trend, icon, onClick }: { label: string; value: string; note: string; trend: string; icon: string; onClick: () => void }) {
  return <button className="stat-card" onClick={onClick}><div className="stat-top"><span>{label}</span><i>{icon}</i></div><strong>{value}</strong><small>{note}</small><em>↗ {trend}</em></button>
}
