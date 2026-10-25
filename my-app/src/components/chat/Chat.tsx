import { useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../../types'
import type { Conversation } from '../../api/campusApi'
import { AIMessage } from './AIMessage'

type Props = {
  messages: ChatMessage[]
  ask: (value: string) => void
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
  threadsOpen: boolean
  closeThreads: () => void
}

const SUGGESTIONS = [
  'What is my attendance?',
  'Which class do I have next?',
  'Summarise my last 5 messages',
  'How much leave do I have left?',
  'When are the end term exams?',
  'Hostel fees for a 2 seater AC room',
]

/** What the assistant is doing, said honestly as time passes. */
const STAGES = [
  { after: 0, text: 'Thinking…' },
  { after: 4, text: 'Looking it up…' },
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
        <div className="message-text thinking-row">
          <span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span>
          <span>{stage.text}</span>
          {seconds >= 4 && <span className="thinking-seconds">{seconds}s</span>}
        </div>
      </div>
    </div>
  )
}

function ThreadList({
  conversations, conversationId, onNewChat, onOpenChat, onRenameChat, onDeleteChat, threadsOpen, closeThreads,
}: Omit<Props, 'messages' | 'ask' | 'thinking'>) {
  const [renaming, setRenaming] = useState('')
  const [draftTitle, setDraftTitle] = useState('')

  const commitRename = (id: string) => {
    const title = draftTitle.trim()
    if (title) onRenameChat(id, title)
    setRenaming('')
  }

  return (
    <aside className={`thread-rail ${threadsOpen ? 'open' : ''}`}>
      <button className="thread-new" type="button" onClick={() => { onNewChat(); closeThreads() }}>+ New chat</button>
      {conversations.length === 0 && <p className="thread-empty">Your chats are saved here once you ask something.</p>}
      <div className="thread-list">
        {conversations.map(thread => (
          <div key={thread.id} className={`thread-item ${thread.id === conversationId ? 'active' : ''}`}>
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
              <button className="thread-open" type="button" onClick={() => { onOpenChat(thread.id); closeThreads() }}>
                <span className="thread-title">{thread.title}</span>
                <span className="thread-meta">{thread.message_count} message(s)</span>
              </button>
            )}
            <span className="thread-actions">
              <button type="button" title="Rename" onClick={() => { setRenaming(thread.id); setDraftTitle(thread.title) }}>✎</button>
              <button type="button" title="Delete" onClick={() => onDeleteChat(thread.id)}>×</button>
            </span>
          </div>
        ))}
      </div>
    </aside>
  )
}

export function Chat(props: Props) {
  const { messages, ask, thinking, conversationId } = props
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, thinking])

  const submit = (value: string) => {
    // One question at a time, so two answers never interleave.
    if (!value.trim() || thinking) return
    setInput('')
    ask(value)
  }

  const lastAi = messages.map(m => m.role).lastIndexOf('ai')
  const fresh = messages.length === 1 && !conversationId

  return (
    <div className="chat-layout">
      <ThreadList {...props} />
      {props.threadsOpen && <button className="rail-overlay" aria-label="Close chat list" onClick={props.closeThreads} />}

      <section className="chat-window">
        <div className="messages" aria-live="polite">
          {messages.map((m, i) => (
            <div key={i} className={`message ${m.role}`}>
              {m.role === 'ai' && <span className="message-avatar">✦</span>}
              <div className="message-content">
                <div className="message-text">{m.role === 'ai' ? <AIMessage text={m.text} /> : m.text}</div>
                {m.role === 'ai' && i === lastAi && (m.model || m.source) && (
                  <div className="message-meta">
                    {m.model && <span>{m.model}</span>}
                    {m.source && <span>{m.source}</span>}
                  </div>
                )}
                {m.role === 'ai' && m.note && <p className="message-note">{m.note}</p>}
              </div>
            </div>
          ))}
          {thinking && <Thinking />}

          {fresh && !thinking && (
            <div className="suggestions">
              {SUGGESTIONS.map(text => (
                <button key={text} onClick={() => submit(text)}>{text}</button>
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form className="chat-input" onSubmit={event => { event.preventDefault(); submit(input) }}>
          <input
            value={input}
            onChange={event => setInput(event.target.value)}
            placeholder={thinking ? 'CampusAI is working…' : 'Ask about your attendance, classes, exams, hostel…'}
            aria-label="Ask CampusAI"
            disabled={thinking}
            autoFocus
          />
          <button type="submit" aria-label="Send" disabled={thinking || !input.trim()}>
            {thinking ? <span className="spinner" /> : '↑'}
          </button>
        </form>
      </section>
    </div>
  )
}
