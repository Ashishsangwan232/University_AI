import { useEffect, useMemo, useState } from 'react'
import type { ChatMessage, Page } from '../types'
import { AIMessage } from '../components/chat/AIMessage'
import { getAgentProviders, type AgentProviders, type Conversation, type StudentProfile } from '../api/campusApi'
import { initials } from '../utils/student'

type Props = {
  input: string
  setInput: (value: string) => void
  messages: ChatMessage[]
  ask: (value: string) => void
  navigate: (page: Page) => void
  student: StudentProfile | null
  /** Which model the student picked, or '' for the backend's default. */
  provider: string
  setProvider: (value: string) => void
  /** True from the moment a question is sent until the answer arrives. */
  thinking: boolean
  /** Saved threads, most recently used first. */
  conversations: Conversation[]
  /** The open thread, or '' for a chat that has not been saved yet. */
  conversationId: string
  onNewChat: () => void
  onOpenChat: (id: string) => void
  onRenameChat: (id: string, title: string) => void
  onDeleteChat: (id: string) => void
}

/**
 * The saved conversations, beside the chat.
 *
 * Every thread is stored by the backend, and reopening one sends its earlier
 * turns to the model with the next question - which is what stops the student
 * having to restate context in every message.
 */
function ThreadList({
  conversations, conversationId, onNewChat, onOpenChat, onRenameChat, onDeleteChat,
}: Pick<Props, 'conversations' | 'conversationId' | 'onNewChat' | 'onOpenChat' | 'onRenameChat' | 'onDeleteChat'>) {
  const [renaming, setRenaming] = useState('')
  const [draftTitle, setDraftTitle] = useState('')

  const commitRename = (id: string) => {
    const title = draftTitle.trim()
    if (title) onRenameChat(id, title)
    setRenaming('')
  }

  return (
    <aside className="thread-rail">
      <button className="thread-new" type="button" onClick={onNewChat}>+ New chat</button>
      {conversations.length === 0 && (
        <p className="thread-empty">Your chats are saved here once you ask something.</p>
      )}
      <div className="thread-list">
        {conversations.map(thread => (
          <div
            key={thread.id}
            className={`thread-item ${thread.id === conversationId ? 'active' : ''}`}
          >
            {renaming === thread.id ? (
              <input
                className="thread-rename"
                value={draftTitle}
                autoFocus
                onChange={event => setDraftTitle(event.target.value)}
                onBlur={() => commitRename(thread.id)}
                onKeyDown={event => {
                  if (event.key === 'Enter') commitRename(thread.id)
                  if (event.key === 'Escape') setRenaming('')
                }}
              />
            ) : (
              <button className="thread-open" type="button" onClick={() => onOpenChat(thread.id)}>
                <span className="thread-title">{thread.title}</span>
                <span className="thread-meta">{thread.message_count} message(s)</span>
              </button>
            )}
            <span className="thread-actions">
              <button
                type="button" title="Rename"
                onClick={() => { setRenaming(thread.id); setDraftTitle(thread.title) }}
              >✎</button>
              <button type="button" title="Delete" onClick={() => onDeleteChat(thread.id)}>×</button>
            </span>
          </div>
        ))}
      </div>
    </aside>
  )
}

/**
 * What the assistant is doing, said honestly as time passes.
 *
 * A question that needs UMS opens the portal in the background and can take
 * most of a minute, so a bare spinner looks stuck. These lines say what is
 * actually happening at each stage rather than inventing progress.
 */
const STAGES = [
  { after: 0, text: 'Thinking…' },
  { after: 4, text: 'Looking up your data…' },
  { after: 12, text: 'Still working — reading from UMS can take a moment.' },
  { after: 30, text: 'Taking longer than usual. UMS is slow to answer sometimes.' },
]

function Thinking() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const timer = window.setInterval(() => setSeconds(value => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [])
  const stage = [...STAGES].reverse().find(item => seconds >= item.after) ?? STAGES[0]

  return (
    <div className="message ai">
      <span className="message-avatar">✦</span>
      <div className="message-content">
        <span className="message-name">CampusAI</span>
        <div className="message-text thinking-row">
          <span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span>
          <span className="thinking-label">{stage.text}</span>
          {seconds >= 4 && <span className="thinking-seconds">{seconds}s</span>}
        </div>
      </div>
    </div>
  )
}

const suggestions = [
  { label: 'Check my attendance', icon: '◔' },
  { label: 'Which class do I have at 1:40 today?', icon: '▦' },
  { label: 'Summarise my last 5 messages', icon: '✉' },
  { label: 'Any important announcements today?', icon: '!' },
  { label: 'Can I take hostel leave this weekend?', icon: '⌂' },
]

function labelFor(models: AgentProviders, id: string): string {
  return models.providers.find(item => item.id === id)?.label ?? id
}

/** One honest line when a model in the list cannot be used yet. */
function unavailableNote(models: AgentProviders): string {
  const missing = models.providers.filter(item => !item.available)
  if (!missing.length) return ''
  return missing.map(item => `${item.label}: ${item.reason}`).join(' ')
}

function getAction(text: string): { label: string; page: Page } | null {
  const value = text.toLowerCase()
  if (value.includes('attendance') || value.includes('miss') || value.includes('skip')) return { label: 'Open Attendance', page: 'attendance' }
  if (value.includes('class') || value.includes('timetable')) return { label: 'View Timetable', page: 'timetable' }
  if (value.includes('announcement') || value.includes('notice')) return { label: 'View Announcements', page: 'announcements' }
  if (value.includes('leave')) return { label: 'Open Hostel Leave', page: 'leave' }
  if (value.includes('service')) return { label: 'Browse Services', page: 'services' }
  return null
}

export function Chat({
  input, setInput, messages, ask, navigate, student, provider, setProvider, thinking,
  conversations, conversationId, onNewChat, onOpenChat, onRenameChat, onDeleteChat,
}: Props) {
  const [showSuggestions, setShowSuggestions] = useState(true)
  const [models, setModels] = useState<AgentProviders | null>(null)

  useEffect(() => {
    let active = true
    getAgentProviders()
      .then(data => { if (active) setModels(data) })
      .catch(() => { /* the chat still works; the switcher just stays hidden */ })
    return () => { active = false }
  }, [])
  const lastAiIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) if (messages[i].role === 'ai') return i
    return -1
  }, [messages])

  const submit = (value: string) => {
    // One question at a time: a second send while the first is still running
    // would interleave two answers.
    if (!value.trim() || thinking) return
    setShowSuggestions(false)
    ask(value)
  }

  return (
    <div className="chat-page">
      <div className="chat-intro">
        <div className="ai-large">✦</div>
        <div>
          <div className="eyebrow">CampusAI assistant</div>
          <h1>Ask CampusAI</h1>
          <p>Ask in plain language. I can use college information and, when connected, your student portal.</p>
        </div>
      </div>

      <div className="chat-capabilities" style={{ alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
        <span>● Attendance</span>
        <span>● Timetable</span>
        <span>● Messages &amp; notices</span>
        <span>● Hostel leave</span>
        {models && models.providers.length > 0 && (
          <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <label htmlFor="model-picker" style={{ opacity: .7 }}>Model</label>
            <select
              id="model-picker"
              value={provider}
              onChange={event => setProvider(event.target.value)}
              style={{ padding: '4px 8px', borderRadius: 8 }}
            >
              <option value="">Default ({labelFor(models, models.default)})</option>
              {models.providers.map(item => (
                <option key={item.id} value={item.id} disabled={!item.available}>
                  {item.label} · {item.model}{item.available ? '' : ' (no key)'}
                </option>
              ))}
            </select>
          </span>
        )}
      </div>
      {models && unavailableNote(models) && (
        <p style={{ fontSize: 12, opacity: .7, margin: '2px 0 8px' }}>{unavailableNote(models)}</p>
      )}

      <div className="chat-layout">
        <ThreadList
          conversations={conversations}
          conversationId={conversationId}
          onNewChat={onNewChat}
          onOpenChat={onOpenChat}
          onRenameChat={onRenameChat}
          onDeleteChat={onDeleteChat}
        />
      <div className="chat-window">
        <div className="messages" aria-live="polite">
          {messages.map((m, i) => {
            const action = m.role === 'ai' ? getAction(m.text) : null
            const isLatestAi = i === lastAiIndex
            return (
              <div key={i} className={`message ${m.role}`}>
                <span className="message-avatar">{m.role === 'ai' ? '✦' : initials(student)}</span>
                <div className="message-content">
                  <span className="message-name">{m.role === 'ai' ? 'CampusAI' : 'You'}</span>
                  <div className="message-text">{m.role === 'ai' ? <AIMessage text={m.text} /> : m.text}</div>
                  {m.role === 'ai' && isLatestAi && (
                    <div className="message-meta">
                      <span>{m.model ?? 'CampusAI response'}</span>
                      <span>•</span><span>{m.source ?? 'CampusAI'}</span>
                      {m.toolUsed && <><span>•</span><span>Tool: {m.toolUsed}</span></>}
                    </div>
                  )}
                  {m.role === 'ai' && m.note && (
                    <p style={{ fontSize: 12, opacity: .75, margin: '6px 0 0' }}>{m.note}</p>
                  )}
                  {action && isLatestAi && (
                    <button className="chat-action" onClick={() => navigate(action.page)}>{action.label} <span>→</span></button>
                  )}
                </div>
              </div>
            )
          })}
          {thinking && <Thinking />}
        </div>

        {showSuggestions && messages.length === 1 && !conversationId && (
          <div className="suggestion-area">
            <span className="suggestion-label">Try asking</span>
            <div className="suggestions">
              {suggestions.map((suggestion) => (
                <button key={suggestion.label} onClick={() => submit(suggestion.label)} disabled={thinking}>
                  <span>{suggestion.icon}</span>{suggestion.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <form className={`chat-input ${thinking ? 'busy' : ''}`} onSubmit={(e) => { e.preventDefault(); submit(input) }}>
          <span className="input-spark" aria-hidden="true">{thinking ? <span className="input-spinner" /> : '✦'}</span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={thinking ? 'CampusAI is working…' : 'Ask about attendance, leave, notices, timetable...'}
            aria-label="Ask CampusAI"
            disabled={thinking}
          />
          <button type="submit" aria-label={thinking ? 'Waiting for an answer' : 'Send message'} disabled={thinking}>
            {thinking ? <span className="input-spinner" /> : '↑'}
          </button>
        </form>
        <small className="chat-disclaimer">
          For important actions, CampusAI will show you the details before anything is submitted.
          {conversationId && ' This chat is saved, so I remember what you already told me.'}
        </small>
      </div>
      </div>
    </div>
  )
}
