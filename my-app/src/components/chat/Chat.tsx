import { useEffect, useRef, useState } from 'react'
import { PiArrowsClockwise, PiCheck, PiCopy, PiSidebarSimple, PiSpeakerHigh, PiSpeakerSlash } from 'react-icons/pi'
import type { ChatMessage } from '../../types'
import type { AgentProviders } from '../../api/campusApi'
import { AIMessage } from './AIMessage'
import { MascotInput, RobotMascot, type Effort } from './MascotInput'

type Props = {
  messages: ChatMessage[]
  /** Send a question with the current model and effort. */
  ask: (prompt: string) => void
  /** Ask the last question again, replacing the last answer. */
  retry: () => void
  cancel: () => void
  /** True from the moment a question is sent until the answer arrives. */
  thinking: boolean
  providers: AgentProviders | null
  provider: string
  effort: Effort
  onProviderChange: (id: string) => void
  onEffortChange: (effort: Effort) => void
  sidebarOpen: boolean
  openSidebar: () => void
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
    <div className="turn ai">
      <div className="thinking-row">
        <span className="thinking-shimmer">{stage.text}</span>
        {seconds >= 4 && <span className="thinking-seconds">{seconds}s</span>}
      </div>
    </div>
  )
}

/** Markdown-ish answer text as plain words, for copying and reading aloud. */
function plain(text: string): string {
  return text
    .replace(/\*\*|__|`/g, '')
    .replace(/^\s*[-*•]\s+/gm, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '$1')
}

function AnswerActions({ text, onRetry, canRetry }: { text: string; onRetry: () => void; canRetry: boolean }) {
  const [copied, setCopied] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const canSpeak = typeof window !== 'undefined' && 'speechSynthesis' in window

  useEffect(() => () => { if (speaking) window.speechSynthesis.cancel() }, [speaking])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(plain(text))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard blocked: nothing to do */ }
  }

  const speak = () => {
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    const utterance = new SpeechSynthesisUtterance(plain(text).replace(/https?:\/\/\S+/g, 'link'))
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
    setSpeaking(true)
  }

  return (
    <div className="answer-actions">
      <button title={copied ? 'Copied' : 'Copy'} aria-label="Copy answer" onClick={copy}>
        {copied ? <PiCheck size={17} /> : <PiCopy size={17} />}
      </button>
      {canSpeak && (
        <button title={speaking ? 'Stop reading' : 'Read aloud'} aria-label={speaking ? 'Stop reading' : 'Read answer aloud'} onClick={speak}>
          {speaking ? <PiSpeakerSlash size={17} /> : <PiSpeakerHigh size={17} />}
        </button>
      )}
      {canRetry && (
        <button title="Ask again" aria-label="Ask again" onClick={onRetry}>
          <PiArrowsClockwise size={17} />
        </button>
      )}
    </div>
  )
}

export function Chat(props: Props) {
  const { messages, ask, retry, cancel, thinking, providers, provider, effort, onProviderChange, onEffortChange } = props
  const bottomRef = useRef<HTMLDivElement>(null)

  // A chat is "fresh" until the student has asked something.
  const fresh = !messages.some(m => m.role === 'user')

  useEffect(() => {
    if (!fresh) bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, thinking, fresh])

  const lastAi = messages.map(m => m.role).lastIndexOf('ai')

  const input = (
    <MascotInput
      onSubmit={ask}
      onCancel={cancel}
      isProcessing={thinking}
      providers={providers}
      provider={provider}
      effort={effort}
      onProviderChange={onProviderChange}
      onEffortChange={onEffortChange}
      menuPlacement={fresh ? 'down' : 'up'}
    />
  )

  return (
    <main className="main">
      <header className="main-top">
        {!props.sidebarOpen && (
          <button className="icon-btn" title="Open sidebar" aria-label="Open sidebar" onClick={props.openSidebar}>
            <PiSidebarSimple size={20} />
          </button>
        )}
        <span className="main-title">CampusAI</span>
      </header>

      {fresh ? (
        <div className="home">
          <div className="home-inner">
            <div className="home-hero">
              <RobotMascot emotion={thinking ? 'thinking' : 'reading'} />
              <h1>What can I help with?</h1>
              <p>Your attendance, classes, notices and leave from UMS — plus anything about LPU.</p>
            </div>
            {input}
            <div className="suggestions">
              {SUGGESTIONS.map(text => (
                // Sends directly with the chosen model and effort - exactly once.
                <button key={text} disabled={thinking} onClick={() => ask(text)}>{text}</button>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="thread" aria-live="polite">
            <div className="thread-inner">
              {messages.map((m, i) => (
                <div key={i} className={`turn ${m.role}`}>
                  {m.role === 'user' ? (
                    <div className="user-bubble">{m.text}</div>
                  ) : (
                    <>
                      <div className="answer"><AIMessage text={m.text} /></div>
                      {m.note && <p className="answer-note">{m.note}</p>}
                      {i === lastAi && !thinking && (
                        <div className="answer-foot">
                          <AnswerActions text={m.text} onRetry={retry} canRetry={i === messages.length - 1} />
                          {(m.model || m.source) && (
                            <span className="answer-meta">{[m.model, m.source].filter(Boolean).join(' · ')}</span>
                          )}
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
              {thinking && <Thinking />}
              <div ref={bottomRef} />
            </div>
          </div>
          <div className="dock">
            {input}
            <p className="disclaimer">CampusAI can make mistakes. Check important info in UMS.</p>
          </div>
        </>
      )}
    </main>
  )
}
