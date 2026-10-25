import { useEffect, useMemo, useState } from 'react'
import { PageTitle } from '../components/ui/PageTitle'
import { getAnnouncements, type AnnouncementItem, type AnnouncementsResponse, type ApiError } from '../api/campusApi'

const cardStyle: React.CSSProperties = {
  border: '1px solid rgba(0,0,0,.10)', borderRadius: 14, padding: '16px 18px',
  display: 'flex', flexDirection: 'column', gap: 8,
}

/** Live UMS announcements, with the same live/demo honesty as Attendance. */
export default function Announcements() {
  const [data, setData] = useState<AnnouncementsResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [onlyAttachments, setOnlyAttachments] = useState(false)
  const [open, setOpen] = useState<AnnouncementItem | null>(null)

  const load = () => {
    setLoading(true)
    getAnnouncements()
      .then(response => { setData(response); setError('') })
      .catch(reason => setError((reason as ApiError).message || 'Could not load announcements.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const items = data?.announcements ?? []
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    return items.filter(item => {
      if (onlyAttachments && item.attachments.length === 0) return false
      if (!query) return true
      return `${item.title} ${item.text} ${item.reference}`.toLowerCase().includes(query)
    })
  }, [items, search, onlyAttachments])

  const withAttachments = items.filter(a => a.attachments.length > 0).length

  return (
    <div className="section-page">
      <PageTitle
        eyebrow={data?.live ? 'Live from UMS' : 'Demo data'}
        title="Announcements"
        desc="Notices published to your UMS account, including the files attached to them."
      />

      {error && (
        <div className="panel empty-state">
          <h2>Announcements unavailable</h2>
          <p>{error}</p>
          <button className="secondary-btn" type="button" onClick={load}>Try again</button>
        </div>
      )}

      {!error && (
        <>
          <div className="announcement-summary">
            <div>
              <span className="eyebrow">{data?.source ?? 'Loading'}</span>
              <h2>{items.length} announcements</h2>
            </div>
            <span className="muted">{filtered.length} shown · {withAttachments} with attachments</span>
          </div>

          <div className="filter-row announcement-filters">
            <div className="filter-buttons">
              <button type="button" className={`filter ${onlyAttachments ? '' : 'active'}`} onClick={() => setOnlyAttachments(false)}>All</button>
              <button type="button" className={`filter ${onlyAttachments ? 'active' : ''}`} onClick={() => setOnlyAttachments(true)}>With attachments</button>
              <button type="button" className="filter" onClick={load}>Refresh</button>
            </div>
            <div className="search">
              <span aria-hidden="true">⌕</span>
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search announcements"
                aria-label="Search announcements"
              />
              {search && <button type="button" className="clear-search" onClick={() => setSearch('')} aria-label="Clear search">×</button>}
            </div>
          </div>

          {loading && <div className="panel empty-state"><p>Reading announcements from UMS…</p></div>}

          <div className="announcement-grid">
            {filtered.map(item => (
              <article key={item.id} className="announcement-card" style={cardStyle}>
                <div className="announcement-card-top">
                  <span className="tag">{item.when || item.date || 'No date'}</span>
                  {item.attachments.length > 0 && (
                    <span className="muted">{item.attachments.length} file{item.attachments.length === 1 ? '' : 's'}</span>
                  )}
                </div>
                <h2 style={{ fontSize: 16, margin: 0 }}>{item.title}</h2>
                <p style={{ margin: 0, opacity: .8 }}>
                  {item.text.length > 220 ? `${item.text.slice(0, 220)}…` : item.text}
                </p>
                <button className="text-btn" type="button" onClick={() => setOpen(item)}>Read announcement →</button>
              </article>
            ))}
          </div>

          {!loading && filtered.length === 0 && (
            <div className="panel empty-state">
              <h2>No announcements found</h2>
              <p>{items.length === 0 ? 'UMS returned no announcements.' : 'Try another search term.'}</p>
              {items.length > 0 && (
                <button className="secondary-btn" type="button" onClick={() => { setSearch(''); setOnlyAttachments(false) }}>Clear filters</button>
              )}
            </div>
          )}
        </>
      )}

      {open && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setOpen(null)}>
          <div className="announcement-modal" role="dialog" aria-modal="true" onMouseDown={e => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <span className="tag">{open.when || open.date || 'No date'}</span>
                {open.reference && <p className="announcement-date" style={{ fontSize: 11 }}>{open.reference}</p>}
              </div>
              <button className="icon-btn" type="button" onClick={() => setOpen(null)} aria-label="Close">×</button>
            </div>
            <h2>{open.title}</h2>
            <p className="announcement-modal-text" style={{ whiteSpace: 'pre-wrap' }}>{open.text}</p>

            {open.attachments.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong style={{ fontSize: 13 }}>Attachments</strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 13 }}>
                  {open.attachments.map(file => (
                    <li key={file.href}>
                      <a href={file.href} target="_blank" rel="noreferrer">{file.name}</a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {open.links.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong style={{ fontSize: 13 }}>Links</strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 13 }}>
                  {open.links.map(link => (
                    <li key={link.href}>
                      <a href={link.href} target="_blank" rel="noreferrer">{link.text || link.href}</a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <div className="modal-footer">
              <button className="secondary-btn" type="button" onClick={() => setOpen(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
