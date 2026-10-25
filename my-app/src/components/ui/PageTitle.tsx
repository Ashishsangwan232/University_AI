export function PageTitle({ eyebrow, title, desc }: { eyebrow: string; title: string; desc: string }) {
  return <div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{desc}</p></div></div>
}
