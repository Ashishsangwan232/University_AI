import { useEffect, useMemo, useState } from 'react'
import { PageTitle } from '../components/ui/PageTitle'
import { getMessages, type ApiError, type MessageItem, type MessagesResponse } from '../api/campusApi'

const rowStyle: React.CSSProperties = {
  border: '1px solid rgba(0,0,0,.10)', borderRadius: 14, padding: '14px 18px',
  display: 'flex', flexDirection: 'column', gap: 6, cursor: 'pointer',
}

/**
 * The UMS inbox. There is no demo equivalent, so when UMS is not connected this
 * says so plainly rather than inventing messages.
 */
export default function Messages() {
  const [data, setData] = useState<MessagesResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState<MessageItem | null>(null)

  const load = () => {
    setLoading(true)
    getMessages()
      .then(response => { setData(response); setError('') })
      .catch(reason => setError((reason as ApiError).message || 'Could not load messages.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const messages = data?.messages ?? []
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return messages
    return messages.filter(m => `${m.title} ${m.sender} ${m.text}`.toLowerCase().includes(query))
  }, [messages, search])

  return (
    <div className="section-page">
      <PageTitle
        eyebrow="Live from UMS"
        title="Messages"
        desc="Your UMS inbox: notices sent to you personally by departments and faculty."
      />

      {error && (
        <div className="panel empty-state">
          <h2>Messages need a UMS session</h2>
          <p>{error}</p>
          <button className="secondary-btn" type="button" onClick={load}>Try again</button>
          <small>Open Profile and click Connect UMS, then sign in yourself in the CampusAI browser window.</small>
        </div>
      )}

      {!error && (
        <>
          <div className="announcement-summary">
            <div>
              <span className="eyebrow">{data?.source ?? 'Loading'}</span>
              <h2>{messages.length} messages</h2>
            </div>
            <span className="muted">{filtered.length} shown</span>
          </div>

          <div className="filter-row announcement-filters">
            <div className="filter-buttons">
              <button type="button" className="filter" onClick={load}>Refresh</button>
            </div>
            <div className="search">
              <span aria-hidden="true">⌕</span>
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search messages"
                aria-label="Search messages"
              />
              {search && <button type="button" className="clear-search" onClick={() => setSearch('')} aria-label="Clear search">×</button>}
            </div>
          </div>

          {loading && <div className="panel empty-state"><p>Reading your UMS inbox…</p></div>}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {filtered.map(message => (
              <article
                key={message.id}
                style={rowStyle}
                onClick={() => setOpen(message)}
                onKeyDown={e => { if (e.key === 'Enter') setOpen(message) }}
                role="button"
                tabIndex={0}
              >
                <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                  <strong style={{ flex: '1 1 auto' }}>{message.title}</strong>
                  {(message.when || message.date) && <span className="muted" style={{ fontSize: 12 }}>{message.when || message.date}</span>}
                </div>
                {message.sender && <small style={{ opacity: .7 }}>From {message.sender}</small>}
                <p style={{ margin: 0, opacity: .8, fontSize: 13 }}>
                  {message.text.length > 200 ? `${message.text.slice(0, 200)}…` : message.text}
                </p>
                {(message.attachments.length > 0 || message.links.length > 0) && (
                  <small style={{ opacity: .65 }}>
                    {message.attachments.length > 0 && `${message.attachments.length} attachment(s)`}
                    {message.attachments.length > 0 && message.links.length > 0 && ' · '}
                    {message.links.length > 0 && `${message.links.length} link(s)`}
                  </small>
                )}
              </article>
            ))}
          </div>

          {!loading && filtered.length === 0 && (
            <div className="panel empty-state">
              <h2>No messages found</h2>
              <p>{messages.length === 0 ? 'Your UMS inbox is empty.' : 'Try another search term.'}</p>
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
                {open.sender && <p className="announcement-date">From {open.sender}</p>}
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
                    <li key={file.href}><a href={file.href} target="_blank" rel="noreferrer">{file.name}</a></li>
                  ))}
                </ul>
              </div>
            )}
            {open.links.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <strong style={{ fontSize: 13 }}>Links</strong>
                <ul style={{ margin: '6px 0 0', paddingLeft: 18, fontSize: 13 }}>
                  {open.links.map(link => (
                    <li key={link.href}><a href={link.href} target="_blank" rel="noreferrer">{link.text || link.href}</a></li>
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
