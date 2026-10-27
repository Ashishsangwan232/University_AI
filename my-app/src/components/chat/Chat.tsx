import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Check, Copy, PanelLeftOpen, RotateCw, Volume2, VolumeX } from 'lucide-react'
import type { ChatMessage } from '../../types'
import type { AgentProviders } from '../../api/campusApi'
import { AnimatedIcon } from '../ui/AnimatedIcon'
import { iconButtonMotion } from '../ui/iconMotion'
import { DynamicText, GreetingPreloader } from '../ui/GreetingPreloader'
import { LoaderGooeyBlobs } from '../ui/LoaderGooeyBlobs'
import { AIMessage } from './AIMessage'
import { LANGUAGES } from './languages'
import { MascotInput, ROBOT_LAYOUT_ID, RobotMascot, type Effort } from './MascotInput'
import { VoiceMode } from './VoiceMode'
import { speakAloud, type SpeakHandle } from './speaker'
import { spokenText } from './speech'

type Props = {
  messages: ChatMessage[]
  /** Send a question with the current model, effort and language. */
  ask: (prompt: string, voice?: boolean) => void
  /** Ask the last question again, replacing the last answer. */
  retry: () => void
  cancel: () => void
  /** True from the moment a question is sent until the answer arrives. */
  thinking: boolean
  providers: AgentProviders | null
  provider: string
  effort: Effort
  language: string
  onProviderChange: (id: string) => void
  onEffortChange: (effort: Effort) => void
  onLanguageChange: (language: string) => void
  sidebarOpen: boolean
  openSidebar: () => void
  /** True while the UMS browser is being opened after "Connect UMS". */
  umsConnecting: boolean
}

const SUGGESTIONS = [
  'Show my attendance as a chart',
  'Which class do I have next?',
  'Summarise my last 5 messages',
  'How do I apply for hostel leave? Show the steps',
  'When are the end term exams?',
  'Compare hostel fees for AC rooms',
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
        <LoaderGooeyBlobs size={9} duration={1.4} color="var(--ok)" />
        <AnimatePresence mode="wait">
          <motion.span
            key={stage.text}
            className="thinking-shimmer"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
          >
            {stage.text}
          </motion.span>
        </AnimatePresence>
        {seconds >= 4 && <span className="thinking-seconds">{seconds}s</span>}
      </div>
    </div>
  )
}

/** Markdown-ish answer text as plain words, for copying and reading aloud. */
function plain(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, '')
    .replace(/\*\*|__|`/g, '')
    .replace(/^\s*[-*•]\s+/gm, '')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '$1')
}

function AnswerActions({ text, onRetry, canRetry }: { text: string; onRetry: () => void; canRetry: boolean }) {
  const [copied, setCopied] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const speakerRef = useRef<SpeakHandle | null>(null)

  useEffect(() => () => speakerRef.current?.stop(), [])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(plain(text))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch { /* clipboard blocked: nothing to do */ }
  }

  // Offline Piper voice (Hindi or English by script), browser voice as fallback.
  const speak = () => {
    if (speaking) {
      speakerRef.current?.stop()
      return
    }
    setSpeaking(true)
    speakerRef.current = speakAloud(spokenText(text, 6000), {
      onDone: () => { speakerRef.current = null; setSpeaking(false) },
    })
  }

  return (
    <div className="answer-actions">
      <motion.button {...iconButtonMotion} title={copied ? 'Copied' : 'Copy'} aria-label="Copy answer" onClick={copy}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={copied ? 'done' : 'copy'}
            initial={{ scale: 0.5, rotate: -45, opacity: 0 }}
            animate={{ scale: 1, rotate: 0, opacity: 1 }}
            exit={{ scale: 0.5, rotate: 45, opacity: 0 }}
            transition={{ duration: 0.18 }}
            style={{ display: 'inline-flex' }}
          >
            {copied ? <Check size={16} className="text-emerald-500" /> : <AnimatedIcon icon={Copy} size={16} motion="pop" />}
          </motion.span>
        </AnimatePresence>
      </motion.button>
      {(
        <motion.button {...iconButtonMotion} title={speaking ? 'Stop reading' : 'Read aloud'} aria-label={speaking ? 'Stop reading' : 'Read answer aloud'} onClick={speak}>
          {speaking
            ? (
              <motion.span animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 0.9, repeat: Infinity }} style={{ display: 'inline-flex' }}>
                <VolumeX size={16} className="text-emerald-500" />
              </motion.span>
            )
            : <AnimatedIcon icon={Volume2} size={16} motion="wiggle" />}
        </motion.button>
      )}
      {canRetry && (
        <motion.button {...iconButtonMotion} title="Ask again" aria-label="Ask again" onClick={onRetry}>
          <AnimatedIcon icon={RotateCw} size={16} motion="spin" />
        </motion.button>
      )}
    </div>
  )
}

export function Chat(props: Props) {
  const {
    messages, ask, retry, cancel, thinking, providers, provider, effort, language,
    onProviderChange, onEffortChange, onLanguageChange,
  } = props
  const bottomRef = useRef<HTMLDivElement>(null)
  // While the student types on the start screen, the robot sits on the bar,
  // so the heading's robot steps away (one robot, not two).
  const [barHasRobot, setBarHasRobot] = useState(false)
  const [voiceOpen, setVoiceOpen] = useState(false)
  // Voice mode listens and speaks in the chosen reply language.
  const speechLang = LANGUAGES.find(l => l.id === language)?.speech ?? ''

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
      language={language}
      onProviderChange={onProviderChange}
      onEffortChange={onEffortChange}
      onLanguageChange={onLanguageChange}
      menuPlacement={fresh ? 'down' : 'up'}
      onTypingChange={setBarHasRobot}
      robotReturnsHome={fresh}
      onVoiceMode={() => setVoiceOpen(true)}
    />
  )

  return (
    <main className="main">
      <VoiceMode
        open={voiceOpen}
        onClose={() => setVoiceOpen(false)}
        ask={ask}
        thinking={thinking}
        messages={messages}
        speechLang={speechLang}
      />
      {/* While UMS opens, the greeting preloader covers the chat area. */}
      <GreetingPreloader
        active={props.umsConnecting}
        loop
        fullPage={false}
        intervalMs={420}
        caption="Opening UMS… sign in in the window that appears"
      />

      <header className="main-top">
        {!props.sidebarOpen && (
          <motion.button {...iconButtonMotion} className="icon-btn" title="Open sidebar" aria-label="Open sidebar" onClick={props.openSidebar}>
            <AnimatedIcon icon={PanelLeftOpen} motion="nudge" size={19} />
          </motion.button>
        )}
        <span className="main-title">CampusAI</span>
      </header>

      {fresh ? (
        <div className="home">
          <div className="home-inner">
            <div className="home-hero">
              {/* Fixed-height slot: the heading stays put while the robot is on the bar. */}
              <div className="home-robot-slot">
                {/* No exit animation on purpose: it disappears in the same frame the
                    bar's robot (same layoutId) appears, and that one animates from
                    here - so there is only ever one robot on screen. */}
                {!barHasRobot && (
                  <motion.div
                    key="hero-robot"
                    layoutId={ROBOT_LAYOUT_ID}
                    transition={{ type: 'spring', stiffness: 320, damping: 26 }}
                  >
                    <RobotMascot emotion={thinking ? 'thinking' : 'reading'} />
                  </motion.div>
                )}
              </div>
              {/* Free time: a slow greeting in many languages. */}
              <DynamicText loop intervalMs={1800} className="home-greeting" />
              <h1>What can I help with?</h1>
              <p>Your attendance, classes, notices and leave from UMS — plus anything about LPU, in your language.</p>
            </div>
            {input}
            <div className="suggestions">
              {SUGGESTIONS.map(text => (
                // Sends directly with the chosen settings - exactly once.
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
                <motion.div
                  key={i}
                  className={`turn ${m.role}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25 }}
                >
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
                </motion.div>
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
