import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import type { ChatMessage } from './types'
import {
  askAgent, deleteConversation, getAgentProviders, getConversation, getConversations, getUMSSessionStatus,
  refreshUMS, renameConversation, startUMSSession, stopUMSSession,
  type AgentProviders, type Conversation, type UMSSessionStatus,
} from './api/campusApi'
import { Chat } from './components/chat/Chat'
import type { Effort } from './components/chat/MascotInput'
import { Sidebar } from './components/layout/Sidebar'
import { UMSBar } from './components/ums/UMSBar'
import { GreetingPreloader } from './components/ui/GreetingPreloader'

function remembered(key: string, fallback: string): string {
  try { return window.localStorage.getItem(key) ?? fallback } catch { return fallback }
}
function remember(key: string, value: string) {
  try { window.localStorage.setItem(key, value) } catch { /* private mode: not remembered */ }
}

const isPhone = () => typeof window !== 'undefined' && window.innerWidth < 820

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [thinking, setThinking] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(() => !isPhone())
  // Model ('' = Auto) and effort live here, so every way of sending - typing,
  // a suggestion, "ask again" - uses the same choice.
  const [provider, setProvider] = useState(() => remembered('campusai.model', ''))
  const [effort, setEffort] = useState<Effort>(() => remembered('campusai.effort', 'medium') as Effort)
  // '' = reply in whatever language the student writes in.
  const [language, setLanguage] = useState(() => remembered('campusai.language', ''))
  const [umsConnecting, setUmsConnecting] = useState(false)
  // Lets the stop button abandon an answer that is still on its way.
  const abortRef = useRef<AbortController | null>(null)
  const [models, setModels] = useState<AgentProviders | null>(null)
  const [umsStatus, setUmsStatus] = useState<UMSSessionStatus | null>(null)
  const [umsBusy, setUmsBusy] = useState(false)
  const [backendDown, setBackendDown] = useState(false)

  const refreshConversations = useCallback(async () => {
    try { setConversations(await getConversations()) } catch { /* chat still works without the list */ }
  }, [])

  useEffect(() => {
    void refreshConversations()
    getAgentProviders().then(setModels).catch(() => { /* menu shows Auto only */ })
  }, [refreshConversations])

  // Keep the UMS card current; the student signs in inside a separate window.
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

  // Connecting opens a browser window, which takes a few seconds: show the
  // greeting preloader meanwhile (at least one full round of greetings).
  const connectUms = async () => {
    setUmsConnecting(true)
    const minimum = new Promise(resolve => window.setTimeout(resolve, 2400))
    await Promise.all([umsAction(startUMSSession), minimum])
    setUmsConnecting(false)
  }

  const startNewChat = () => {
    setConversationId('')
    setMessages([])
  }

  const openChat = async (id: string) => {
    try {
      const thread = await getConversation(id)
      setConversationId(thread.id)
      setMessages(thread.messages.map(message => ({
        role: message.role === 'assistant' ? 'ai' as const : 'user' as const,
        text: message.content,
        source: message.source || undefined,
        toolUsed: message.tool_used || undefined,
        model: message.model ? `${message.provider} · ${message.model}` : undefined,
      })))
    } catch (reason) {
      setMessages(current => [...current, { role: 'ai', text: reason instanceof Error ? reason.message : 'That chat could not be opened.' }])
    }
  }

  // Keep the open chat in the address bar, so a refresh reopens it instead of
  // starting a new chat.
  useEffect(() => {
    const url = new URL(window.location.href)
    if (conversationId) url.searchParams.set('chat', conversationId)
    else url.searchParams.delete('chat')
    window.history.replaceState(null, '', url)
  }, [conversationId])

  // Read before the effect above rewrites the address.
  const [chatToRestore] = useState(() => new URL(window.location.href).searchParams.get('chat'))
  const restoredRef = useRef(false)
  useEffect(() => {
    if (restoredRef.current || !chatToRestore) return
    restoredRef.current = true
    getConversation(chatToRestore)
      .then(thread => {
        setConversationId(thread.id)
        setMessages(thread.messages.map(message => ({
          role: message.role === 'assistant' ? 'ai' as const : 'user' as const,
          text: message.content,
          source: message.source || undefined,
          toolUsed: message.tool_used || undefined,
          model: message.model ? `${message.provider} · ${message.model}` : undefined,
        })))
      })
      .catch(() => setConversationId('')) // deleted or unknown: start fresh
  }, [chatToRestore])

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

  /** Send a question. `showQuestion` is false when re-asking the last one;
   *  `voice` asks for a short spoken answer (voice mode). */
  const send = async (prompt: string, showQuestion = true, voice = false) => {
    const clean = prompt.trim()
    if (!clean || thinking) return
    if (showQuestion) setMessages(current => [...current, { role: 'user', text: clean }])
    setThinking(true)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const response = await askAgent(clean, {
        provider: provider || undefined,
        conversationId: conversationId || undefined,
        effort,
        language: language || undefined,
        voice,
        signal: controller.signal,
      })
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
      const stopped = reason instanceof DOMException && reason.name === 'AbortError'
      setMessages(current => [...current, {
        role: 'ai',
        text: stopped
          ? 'Stopped. (The answer may still be saved to this chat when the server finishes.)'
          : reason instanceof Error ? reason.message : 'I could not reach the CampusAI backend.',
      }])
    } finally {
      abortRef.current = null
      setThinking(false)
    }
  }

  const retry = () => {
    const lastQuestion = [...messages].reverse().find(m => m.role === 'user')
    if (!lastQuestion || thinking) return
    // Drop the last answer, then ask the same question again.
    setMessages(current => (current.length && current[current.length - 1].role === 'ai' ? current.slice(0, -1) : current))
    void send(lastQuestion.text, false)
  }

  return (
    <div className={`app ${sidebarOpen ? 'with-sidebar' : ''}`}>
      {/* Start-up: greetings in many languages, then the overlay slides away. */}
      <GreetingPreloader oncePerSession="campusai.intro" />
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        ums={(
          <UMSBar
            status={umsStatus}
            backendDown={backendDown}
            busy={umsBusy}
            onConnect={() => void connectUms()}
            onRefresh={() => umsAction(refreshUMS)}
            onDisconnect={() => umsAction(stopUMSSession)}
          />
        )}
        conversations={conversations}
        conversationId={conversationId}
        busy={thinking}
        onNewChat={startNewChat}
        onOpenChat={openChat}
        onRenameChat={renameChat}
        onDeleteChat={removeChat}
      />
      {sidebarOpen && <button className="sidebar-scrim" aria-label="Close sidebar" onClick={() => setSidebarOpen(false)} />}

      <Chat
        messages={messages}
        ask={(prompt, voice) => void send(prompt, true, voice)}
        retry={retry}
        cancel={() => abortRef.current?.abort()}
        thinking={thinking}
        providers={models}
        provider={provider}
        effort={effort}
        onProviderChange={id => { setProvider(id); remember('campusai.model', id) }}
        onEffortChange={level => { setEffort(level); remember('campusai.effort', level) }}
        language={language}
        onLanguageChange={lang => { setLanguage(lang); remember('campusai.language', lang) }}
        umsConnecting={umsConnecting}
        sidebarOpen={sidebarOpen}
        openSidebar={() => setSidebarOpen(true)}
      />
    </div>
  )
}

export default App
