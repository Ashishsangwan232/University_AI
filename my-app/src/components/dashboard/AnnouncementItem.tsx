import type { Announcement } from '../../types'

export function AnnouncementItem({ item, first }: { item: Announcement; first?: boolean }) {
  return <div className={`announcement-item ${first ? 'highlight' : ''}`}><div className="announcement-date"><strong>{item.date.split(' ')[1]}</strong><span>{item.date.split(' ')[0]}</span></div><div className="announcement-text"><div><span className={`tag ${item.tag === 'Important' ? 'important' : ''}`}>{item.tag}</span><span className="announcement-time">Today</span></div><strong>{item.title}</strong><p>{item.text}</p></div><button>→</button></div>
}
