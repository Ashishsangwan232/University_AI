import { useCallback, useEffect, useState } from 'react'
import './App.css'
import type { ChatMessage } from './types'
import {
  askAgent, deleteConversation, getAgentProviders, getConversation, getConversations, getUMSSessionStatus,
  refreshUMS, renameConversation, startUMSSession, stopUMSSession,
  type AgentProviders, type Conversation, type UMSSessionStatus,
} from './api/campusApi'
import { Chat } from './components/chat/Chat'
import { UMSBar } from './components/ums/UMSBar'

const WELCOME = 'Hi! I’m CampusAI. Ask me about your attendance, timetable, notices, messages or hostel leave, or anything about LPU — contacts, rules, exam dates, hostel fees and more.'

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'ai', text: WELCOME }])
  const [thinking, setThinking] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState('')
  const [threadsOpen, setThreadsOpen] = useState(false)
  // '' means "whatever the backend is configured to use".
  const [provider, setProvider] = useState('')
  const [models, setModels] = useState<AgentProviders | null>(null)
  const [umsStatus, setUmsStatus] = useState<UMSSessionStatus | null>(null)
  const [umsBusy, setUmsBusy] = useState(false)
  const [backendDown, setBackendDown] = useState(false)

  const refreshConversations = useCallback(async () => {
    try { setConversations(await getConversations()) } catch { /* chat still works without the list */ }
  }, [])

  useEffect(() => {
    void refreshConversations()
    getAgentProviders().then(setModels).catch(() => { /* picker stays hidden */ })
  }, [refreshConversations])

  // Keep the UMS bar current; the student signs in inside a separate window.
  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const status = await getUMSSessionStatus()
        if (active) { setUmsStatus(status); setBackendDown(false) }
      } catch {
        if (active) setBackendDown(true)
      }
    }
    void poll()
    const timer = window.setInterval(poll, 3000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  const umsAction = async (action: () => Promise<UMSSessionStatus>) => {
    setUmsBusy(true)
    try { setUmsStatus(await action()) } catch { /* the next poll shows the real state */ } finally { setUmsBusy(false) }
  }

  const startNewChat = () => {
    setConversationId('')
    setMessages([{ role: 'ai', text: WELCOME }])
  }

  const openChat = async (id: string) => {
    try {
      const thread = await getConversation(id)
      setConversationId(thread.id)
      setMessages(thread.messages.length
        ? thread.messages.map(message => ({
            role: message.role === 'assistant' ? 'ai' as const : 'user' as const,
            text: message.content,
            source: message.source || undefined,
            toolUsed: message.tool_used || undefined,
            model: message.model ? `${message.provider} · ${message.model}` : undefined,
          }))
        : [{ role: 'ai', text: WELCOME }])
    } catch (reason) {
      setMessages(current => [...current, { role: 'ai', text: reason instanceof Error ? reason.message : 'That chat could not be opened.' }])
    }
  }

  const renameChat = async (id: string, title: string) => {
    try { await renameConversation(id, title); await refreshConversations() } catch { /* cosmetic */ }
  }

  const removeChat = async (id: string) => {
    try {
      await deleteConversation(id)
      if (id === conversationId) startNewChat()
      await refreshConversations()
    } catch { /* leave it in the list if the delete failed */ }
  }

  const ask = async (text: string) => {
    const clean = text.trim()
    if (!clean) return
    setMessages(current => [...current, { role: 'user', text: clean }])
    setThinking(true)
    try {
      const response = await askAgent(clean, provider || undefined, conversationId || undefined)
      if (response.conversation_id && response.conversation_id !== conversationId) setConversationId(response.conversation_id)
      void refreshConversations()
      const fellBack = response.fell_back_from ?? []
      setMessages(current => [...current, {
        role: 'ai',
        text: response.answer,
        source: response.source,
        toolUsed: response.tool_used,
        model: response.provider_label ? `${response.provider_label}${response.model ? ` · ${response.model}` : ''}` : undefined,
        // Never hide a fallback: if the chosen model did not answer, say so.
        note: response.note || (fellBack.length
          ? `${fellBack.map(item => item.provider).join(', ')} could not answer, so ${response.provider_label || response.provider} did.`
          : undefined),
      }])
    } catch (reason) {
      setMessages(current => [...current, { role: 'ai', text: reason instanceof Error ? reason.message : 'I could not reach the CampusAI backend.' }])
    } finally {
      setThinking(false)
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <button className="menu-btn" aria-label="Show saved chats" onClick={() => setThreadsOpen(open => !open)}>☰</button>
        <div className="brand"><span className="brand-mark">✦</span>CampusAI</div>
        {models && models.providers.length > 0 && (
          <select className="model-picker" aria-label="Model" value={provider} onChange={event => setProvider(event.target.value)}>
            <option value="">Default model</option>
            {models.providers.map(item => (
              <option key={item.id} value={item.id} disabled={!item.available}>
                {item.label}{item.available ? '' : ' (no key)'}
              </option>
            ))}
          </select>
        )}
      </header>

      {backendDown ? (
        <div className="ums-bar off"><span className="ums-dot" /><div className="ums-text"><strong>Backend not reachable</strong><span>Start FastAPI with: uvicorn app.main:app --reload</span></div></div>
      ) : (
        <UMSBar
          status={umsStatus}
          busy={umsBusy}
          onConnect={() => umsAction(startUMSSession)}
          onRefresh={() => umsAction(refreshUMS)}
          onDisconnect={() => umsAction(stopUMSSession)}
        />
      )}

      <Chat
        messages={messages}
        ask={ask}
        thinking={thinking}
        conversations={conversations}
        conversationId={conversationId}
        onNewChat={startNewChat}
        onOpenChat={openChat}
        onRenameChat={renameChat}
        onDeleteChat={removeChat}
        threadsOpen={threadsOpen}
        closeThreads={() => setThreadsOpen(false)}
      />
    </div>
  )
}

export default App
