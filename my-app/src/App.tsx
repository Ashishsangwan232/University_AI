import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import type { ChatMessage, Page } from './types'
import {
  askAgent, deleteConversation, getAttendance, getConversation, getConversations, getStudent,
  getUMSSessionStatus, refreshUMS, renameConversation, startUMSSession,
  type ApiError, type AttendanceResponse, type Conversation, type StudentProfile,
  type UMSSessionStatus,
} from './api/campusApi'
import { Sidebar } from './components/layout/Sidebar'
import { Topbar } from './components/layout/Topbar'
import { UMSBanner } from './components/ums/UMSBanner'
import { Dashboard } from './pages/Dashboard'
import { Chat } from './pages/Chat'
import { Attendance } from './pages/Attendance'
import Timetable from './pages/Timetable'
import Announcements from './pages/Announcements'
import Messages from './pages/Messages'
import Leave from './pages/Leave'
import { Services } from './pages/Services'
import { Profile } from './pages/Profile'

// Pages that show attendance numbers. Only these wait for live attendance;
// every other page (chat, timetable, leave, ...) works without it.
const NEEDS_ATTENDANCE = new Set<Page>(['dashboard', 'attendance'])

const WELCOME ='Hi! I’m your college assistant. Ask me about attendance, your timetable, notices, hostel leave, or the college website.'

function App() {
  const [page, setPage] = useState<Page>('dashboard')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [chatInput, setChatInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'ai', text: WELCOME }])
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [portalConnected, setPortalConnected] = useState(false)
  const [student, setStudent] = useState<StudentProfile | null>(null)
  const [attendance, setAttendance] = useState<AttendanceResponse | null>(null)
  const [attendanceError, setAttendanceError] = useState('')
  const [studentError, setStudentError] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [umsStatus, setUmsStatus] = useState<UMSSessionStatus | null>(null)
  const [umsConnecting, setUmsConnecting] = useState(false)
  // '' means "whatever the backend is configured to use". The Chat page's
  // switcher sets this; the answer says which model actually replied.
  const [provider, setProvider] = useState('')
  // True while a question is in flight, so the Chat page can show that the
  // assistant is working. A UMS-backed answer can take most of a minute.
  const [thinking, setThinking] = useState(false)
  // Saved chat threads. The backend keeps the messages; this holds which one
  // is open and the list shown beside the chat.
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationId, setConversationId] = useState('')

  // Tracks which capture the UI is already showing, so a *new* capture always
  // triggers a refetch. The previous version only refetched when attendance was
  // still null, which never happened after the first (demo) load - that is why
  // the demo numbers stayed on screen after a successful UMS login.
  const shownCaptureRef = useRef<number | null>(null)
  // Re-read the student's identity the moment UMS becomes authenticated, so the
  // name in the sidebar stops being blank without waiting for a reload.
  const authenticatedRef = useRef<boolean | null>(null)

  const loadStudent = useCallback(async () => {
    try {
      const data = await getStudent()
      setStudent(data)
      setStudentError('')
      if (data.portal_connected) setPortalConnected(true)
      return data
    } catch (reason) {
      const failure = reason as ApiError
      setStudentError(failure.message || 'Your student details could not be read.')
      if (failure.status !== 409) throw failure
      // UMS is connected but the name could not be read. Stay usable and
      // nameless rather than putting a demo student's name on the screen.
      const unknown: StudentProfile = { id: '', name: '', portal_connected: false, live: false }
      setStudent(unknown)
      return unknown
    }
  }, [])

  const loadAttendance = useCallback(async () => {
    try {
      const data = await getAttendance()
      setAttendance(data)
      setAttendanceError('')
      if (data.live) setPortalConnected(true)
      return data
    } catch (reason) {
      const failure = reason as ApiError
      // A 409 means "UMS is connected but live data is not available". Keep the
      // app usable and say so explicitly rather than silently showing demo data.
      setAttendanceError(failure.message || 'Live attendance is unavailable.')
      if (failure.status !== 409) throw failure
      return null
    }
  }, [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    Promise.all([loadStudent(), loadAttendance()])
      .catch(reason => {
        if (!active) return
        setError(reason instanceof Error ? reason.message : 'Unable to connect to the CampusAI backend.')
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [retryKey, loadAttendance, loadStudent])

  useEffect(() => {
    let active = true
    const poll = async () => {
      try {
        const status = await getUMSSessionStatus()
        if (!active) return
        setUmsStatus(status)
        const stamp = status.attendance_captured ? status.attendance_updated_at : null
        if (stamp !== shownCaptureRef.current) {
          shownCaptureRef.current = stamp
          await loadAttendance()
        }
        if (status.authenticated !== authenticatedRef.current) {
          authenticatedRef.current = status.authenticated
          if (status.authenticated) await loadStudent()
        }
      } catch {
        // Backend startup / connection problems are surfaced by the main load.
      }
    }
    void poll()
    const timer = window.setInterval(poll, 2500)
    return () => { active = false; window.clearInterval(timer) }
  }, [loadAttendance, loadStudent])

  const connectUms = async () => {
    setUmsConnecting(true)
    try {
      setUmsStatus(await startUMSSession())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not start the UMS browser.')
    } finally {
      setUmsConnecting(false)
    }
  }

  const refreshUmsSession = async () => {
    try {
      const status = await refreshUMS()
      setUmsStatus(status)
      shownCaptureRef.current = status.attendance_captured ? status.attendance_updated_at : null
      await Promise.all([loadAttendance(), loadStudent()])
    } catch (reason) {
      const failure = reason as ApiError
      setAttendanceError(failure.message || 'Could not refresh the UMS session.')
      if (failure.diagnostics) {
        setUmsStatus(current => current && { ...current, diagnostics: { ...current.diagnostics, ...failure.diagnostics } })
      }
    }
  }

  const subjects = attendance?.subjects ?? []
  // Use the backend aggregate. When UMS reports its own overall percentage we
  // must show that number, not a client-side recomputation.
  const overall = attendance?.overall_percentage ?? 0

  const navigate = (next: Page) => {
    setPage(next)
    setSidebarOpen(false)
  }

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await getConversations())
    } catch {
      // The chat still works without the list; only history browsing is lost.
    }
  }, [])

  useEffect(() => { void refreshConversations() }, [refreshConversations])

  const startNewChat = () => {
    setConversationId('')
    setMessages([{ role: 'ai', text: WELCOME }])
  }

  const openChat = async (id: string) => {
    try {
      const thread = await getConversation(id)
      setConversationId(thread.id)
      setMessages(
        thread.messages.length
          ? thread.messages.map(message => ({
              role: message.role === 'assistant' ? 'ai' as const : 'user' as const,
              text: message.content,
              source: message.source || undefined,
              toolUsed: message.tool_used || undefined,
              model: message.model ? `${message.provider} · ${message.model}` : undefined,
            }))
          : [{ role: 'ai', text: WELCOME }],
      )
    } catch (reason) {
      setMessages(current => [...current, {
        role: 'ai',
        text: reason instanceof Error ? reason.message : 'That conversation could not be opened.',
        source: 'Backend error',
      }])
    }
  }

  const renameChat = async (id: string, title: string) => {
    try {
      await renameConversation(id, title)
      await refreshConversations()
    } catch { /* the title is cosmetic; a failure need not interrupt the chat */ }
  }

  const removeChat = async (id: string) => {
    try {
      await deleteConversation(id)
      if (id === conversationId) startNewChat()
      await refreshConversations()
    } catch { /* leave the thread in the list if the delete failed */ }
  }

  const ask = async (text: string) => {
    const clean = text.trim()
    if (!clean) return
    setMessages(current => [...current, { role: 'user', text: clean }])
    setChatInput('')
    setThinking(true)
    try {
      const response = await askAgent(clean, provider || undefined, conversationId || undefined)
      // The first message of a new thread comes back with its id and title.
      if (response.conversation_id && response.conversation_id !== conversationId) {
        setConversationId(response.conversation_id)
      }
      void refreshConversations()
      const fellBack = response.fell_back_from ?? []
      setMessages(current => [...current, {
        role: 'ai',
        text: response.answer,
        source: response.source,
        toolUsed: response.tool_used,
        model: response.provider_label
          ? `${response.provider_label}${response.model ? ` · ${response.model}` : ''}`
          : undefined,
        // Never hide a fallback: if the chosen model did not answer, say so.
        note: response.note || (fellBack.length
          ? `${fellBack.map(item => item.provider).join(', ')} could not answer, so ${response.provider_label || response.provider} did.`
          : undefined),
      }])
    } catch (reason) {
      setMessages(current => [...current, { role: 'ai', text: reason instanceof Error ? reason.message : 'I could not reach the CampusAI agent.', source: 'Backend error' }])
    } finally {
      setThinking(false)
    }
  }

  if (loading) return <div className="app-shell"><main className="main-content"><div className="backend-state"><div className="backend-state-icon">↔</div><h1>Connecting to CampusAI</h1><p>Loading your student profile and attendance from the backend.</p></div></main></div>

  if (error || !student) {
    return <div className="app-shell"><main className="main-content"><div className="backend-state error">
      <div className="backend-state-icon">!</div>
      <h1>Backend connection failed</h1>
      <p>{error || 'Student data could not be loaded.'}</p>
      <button className="secondary-btn" onClick={() => setRetryKey(value => value + 1)}>Retry</button>
      <small>Make sure FastAPI is running at http://127.0.0.1:8000.</small>
    </div></main></div>
  }

  const pageContent = {
    dashboard: <Dashboard overall={overall} subjects={subjects} student={student} navigate={navigate} />,
    chat: <Chat
      input={chatInput} setInput={setChatInput} messages={messages} ask={ask} navigate={navigate}
      student={student} provider={provider} setProvider={setProvider} thinking={thinking}
      conversations={conversations} conversationId={conversationId}
      onNewChat={startNewChat} onOpenChat={openChat} onRenameChat={renameChat} onDeleteChat={removeChat}
    />,
    attendance: <Attendance overall={overall} subjects={subjects} live={attendance?.live ?? false} source={attendance?.source ?? ''} />,
    timetable: <Timetable />,
    announcements: <Announcements />,
    messages: <Messages />,
    leave: <Leave />,
    services: <Services navigate={navigate} />,
    profile: <Profile student={student} studentError={studentError} portalConnected={portalConnected} umsStatus={umsStatus} onConnectUms={connectUms} onRefreshUms={refreshUmsSession} />,
  }[page]

  return <div className="app-shell">
    {sidebarOpen && <button className="sidebar-overlay" aria-label="Close menu" onClick={() => setSidebarOpen(false)} />}
    <Sidebar page={page} open={sidebarOpen} navigate={navigate} student={student} portalConnected={portalConnected} />
    <main className="main-content">
      <Topbar page={page} onMenu={() => setSidebarOpen(open => !open)} notificationsOpen={notificationsOpen} setNotificationsOpen={setNotificationsOpen} navigate={navigate} student={student} />
      <div className="page-container">
        {(page === 'dashboard' || page === 'attendance' || page === 'profile') && (
          <UMSBanner
            status={umsStatus}
            attendance={attendance}
            attendanceError={attendanceError}
            connecting={umsConnecting}
            onConnect={connectUms}
            onRefresh={refreshUmsSession}
          />
        )}
        {attendance || !NEEDS_ATTENDANCE.has(page) ? pageContent : <div className="backend-state error"><div className="backend-state-icon">!</div><h1>Live UMS attendance not ready</h1><p>{attendanceError}</p><button className="secondary-btn" onClick={refreshUmsSession}>Refresh from UMS</button><button className="text-btn" onClick={() => navigate('chat')}>Open chat instead →</button></div>}
      </div>
    </main>
  </div>
}

export default App
