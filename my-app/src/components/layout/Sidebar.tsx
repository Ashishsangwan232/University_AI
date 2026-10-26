import { useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import { PanelLeftClose, Pencil, Search, SquarePen, Trash2 } from 'lucide-react'
import type { Conversation } from '../../api/campusApi'
import { AnimatedIcon } from '../ui/AnimatedIcon'
import { iconButtonMotion } from '../ui/iconMotion'
import { BrandMark } from '../ui/BrandMark'

type Props = {
  open: boolean
  onClose: () => void
  /** The UMS status card, shown right under the name. */
  ums: ReactNode
  conversations: Conversation[]
  conversationId: string
  busy: boolean
  onNewChat: () => void
  onOpenChat: (id: string) => void
  onRenameChat: (id: string, title: string) => void
  onDeleteChat: (id: string) => void
}

export function Sidebar({
  open, onClose, ums, conversations, conversationId, busy, onNewChat, onOpenChat, onRenameChat, onDeleteChat,
}: Props) {
  const [searching, setSearching] = useState(false)
  const [query, setQuery] = useState('')
  const [renaming, setRenaming] = useState('')
  const [draftTitle, setDraftTitle] = useState('')

  const shown = query.trim()
    ? conversations.filter(c => c.title.toLowerCase().includes(query.trim().toLowerCase()))
    : conversations

  const commitRename = (id: string) => {
    const title = draftTitle.trim()
    if (title) onRenameChat(id, title)
    setRenaming('')
  }

  // On a phone the sidebar is an overlay, so picking something closes it.
  const closeOnPhone = () => { if (window.innerWidth < 820) onClose() }

  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-top">
        <div className="brand"><BrandMark />CampusAI</div>
        <motion.button {...iconButtonMotion} className="icon-btn" title="Close sidebar" aria-label="Close sidebar" onClick={onClose}>
          <AnimatedIcon icon={PanelLeftClose} motion="nudge" size={19} />
        </motion.button>
      </div>

      {ums}

      <nav className="sidebar-nav">
        <motion.button {...iconButtonMotion} className="nav-item" onClick={() => { onNewChat(); closeOnPhone() }} disabled={busy}>
          <AnimatedIcon icon={SquarePen} motion="wiggle" size={17} /> New chat
        </motion.button>
        <motion.button {...iconButtonMotion} className={`nav-item ${searching ? 'active' : ''}`} onClick={() => { setSearching(s => !s); setQuery('') }}>
          <AnimatedIcon icon={Search} motion="pop" size={17} /> Search chats
        </motion.button>
        {searching && (
          <input
            className="sidebar-search"
            placeholder="Search by title…"
            value={query}
            autoFocus
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Escape') { setSearching(false); setQuery('') } }}
          />
        )}
      </nav>

      <div className="sidebar-section">Chats</div>
      <div className="thread-list">
        {shown.length === 0 && (
          <p className="thread-empty">{query ? 'No chats match.' : 'Your chats appear here.'}</p>
        )}
        {shown.map(thread => (
          <div key={thread.id} className={`thread-item ${thread.id === conversationId ? 'active' : ''}`}>
            {renaming === thread.id ? (
              <input
                className="thread-rename"
                value={draftTitle}
                autoFocus
                onChange={e => setDraftTitle(e.target.value)}
                onBlur={() => commitRename(thread.id)}
                onKeyDown={e => {
                  if (e.key === 'Enter') commitRename(thread.id)
                  if (e.key === 'Escape') setRenaming('')
                }}
              />
            ) : (
              <button className="thread-open" title={thread.title} onClick={() => { onOpenChat(thread.id); closeOnPhone() }}>
                {thread.title}
              </button>
            )}
            <span className="thread-actions">
              <motion.button {...iconButtonMotion} title="Rename" aria-label="Rename chat" onClick={() => { setRenaming(thread.id); setDraftTitle(thread.title) }}>
                <AnimatedIcon icon={Pencil} motion="wiggle" size={14} />
              </motion.button>
              <motion.button {...iconButtonMotion} title="Delete" aria-label="Delete chat" onClick={() => onDeleteChat(thread.id)}>
                <AnimatedIcon icon={Trash2} motion="shake" size={14} />
              </motion.button>
            </span>
          </div>
        ))}
      </div>

      <div className="sidebar-foot">LPU student assistant</div>
    </aside>
  )
}
