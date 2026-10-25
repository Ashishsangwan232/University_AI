export function Step({ n, title, text }: { n: string; title: string; text: string }) { return <div className="step"><span>{n}</span><div><strong>{title}</strong><p>{text}</p></div></div> }
