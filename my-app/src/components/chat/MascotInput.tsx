// Chat input with the robot mascot. Adapted from the "AI mascot input"
// reference component: same look and animations, wired to CampusAI's real
// models (from the backend) and a real reasoning-effort setting. File
// attachments and web search are left out because the backend can't use them.
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  PiArrowUpBold, PiCaretDownBold, PiCheckBold, PiMicrophoneBold, PiMicrophoneFill, PiSparkleFill, PiStopFill,
} from 'react-icons/pi'
import { SiOllama } from 'react-icons/si'
import type { AgentProviders } from '../../api/campusApi'

type IconProps = { size?: number; className?: string }

const GeminiIcon = ({ size = 16, className = '' }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81" />
  </svg>
)

export type Effort = 'low' | 'medium' | 'high'

const LEVELS: { id: Effort; label: string; desc: string }[] = [
  { id: 'low', label: 'Low', desc: 'Fastest answers, light reasoning' },
  { id: 'medium', label: 'Medium', desc: 'Balanced - the model’s usual setting' },
  { id: 'high', label: 'High', desc: 'Most careful reasoning, slower' },
]

type ModelOption = {
  /** '' = whatever the backend is configured to use. */
  id: string
  name: string
  detail: string
  available: boolean
  icon: React.ComponentType<IconProps>
  color: string
}

function modelOptions(providers: AgentProviders | null): ModelOption[] {
  const iconFor = (id: string) => (id === 'gemini' ? GeminiIcon : id === 'ollama' ? SiOllama : PiSparkleFill)
  const colorFor = (id: string) => (id === 'gemini' ? 'text-blue-500' : id === 'ollama' ? 'text-zinc-700 dark:text-zinc-200' : 'text-emerald-500')
  const auto: ModelOption = {
    id: '',
    name: 'Auto',
    detail: providers
      ? `Uses ${providers.providers.find(p => p.id === providers.default)?.label ?? providers.default}, falls back if it fails`
      : 'Backend default',
    available: true,
    icon: PiSparkleFill,
    color: 'text-emerald-500',
  }
  return [auto, ...(providers?.providers ?? []).map(p => ({
    id: p.id,
    name: p.label,
    detail: p.available ? p.model : `Unavailable: ${p.reason || 'no API key'}`,
    available: p.available,
    icon: iconFor(p.id),
    color: colorFor(p.id),
  }))]
}

// ------------------------------------------------------------------ mascot
type Emotion = 'reading' | 'thinking'

function EyeLED({ emotion, isBlinking, offsetX }: { emotion: Emotion; isBlinking: boolean; offsetX: number }) {
  if (emotion === 'thinking') {
    return (
      <motion.div
        className="w-2.5 h-3.5 rounded-xs bg-amber-300 shadow-[0_0_10px_#facc15,0_0_18px_rgba(250,204,21,0.4)]"
        animate={{ y: [-1, -3, -1] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
      />
    )
  }
  if (isBlinking) return <div className="w-2.5 h-1 rounded-xs bg-emerald-400 shadow-[0_0_6px_#10b981]" />
  return (
    <motion.div
      className="w-2.5 h-4.5 rounded-xs bg-emerald-400 shadow-[0_0_12px_#34d399,0_0_20px_rgba(52,211,153,0.45)]"
      animate={{ x: offsetX }}
      transition={{ type: 'spring', stiffness: 300, damping: 25 }}
    />
  )
}

export function RobotMascot({ emotion, textLength = 0, isListening = false }: { emotion: Emotion; textLength?: number; isListening?: boolean }) {
  const [isBlinking, setIsBlinking] = useState(false)

  useEffect(() => {
    const interval = setInterval(() => {
      if (emotion !== 'thinking') {
        setIsBlinking(true)
        setTimeout(() => setIsBlinking(false), 140)
      }
    }, 2800 + Math.random() * 2200)
    return () => clearInterval(interval)
  }, [emotion])

  // The eyes follow the text as it grows.
  const eyeOffset = Math.sin(textLength * 0.45) * 6
  const ear = isListening
    ? 'bg-red-500 shadow-[0_0_10px_#ef4444,0_0_18px_rgba(239,68,68,0.7)] animate-pulse'
    : emotion === 'thinking'
      ? 'bg-amber-400 shadow-[0_0_8px_#facc15]'
      : 'bg-emerald-400 shadow-[0_0_8px_#10b981]'

  return (
    <motion.div
      className="relative flex flex-col items-center justify-center select-none px-2.5 pt-2"
      animate={{ y: emotion === 'thinking' ? [0, -5, 0] : [0, -2, 0] }}
      transition={{ y: { duration: 2.2, repeat: Infinity, ease: 'easeInOut' } }}
    >
      <div className="relative w-20 flex justify-between px-2 -mb-2 z-0">
        <div className="w-3.5 h-4 bg-zinc-300 dark:bg-zinc-700 border-2 border-black/10 dark:border-white/10 rounded-tl-xl" />
        <div className="w-3.5 h-4 bg-zinc-300 dark:bg-zinc-700 border-2 border-black/10 dark:border-white/10 rounded-tr-xl" />
      </div>
      <div className="relative flex items-center justify-center">
        <div className={`absolute -left-1.5 w-1 h-5 rounded-l-xs transition-all duration-300 ${ear}`} />
        <div className={`absolute -right-1.5 w-1 h-5 rounded-r-xs transition-all duration-300 ${ear}`} />
        <div className="z-10 w-22 h-15 rounded-xl bg-zinc-100 dark:bg-zinc-800 border-2 border-black/10 dark:border-white/20 flex items-center justify-center p-1.5 shadow-[0_3px_10px_rgba(0,0,0,0.05)] dark:shadow-[0_4px_16px_rgba(0,0,0,0.4)]">
          <div className="relative w-full h-full bg-[#050505] rounded-lg flex items-center justify-center gap-3.5 overflow-hidden shadow-[inset_0_2px_5px_rgba(0,0,0,0.95)]">
            <div className="relative z-10 flex items-center justify-center gap-3.5">
              <EyeLED emotion={emotion} isBlinking={isBlinking} offsetX={eyeOffset} />
              <EyeLED emotion={emotion} isBlinking={isBlinking} offsetX={eyeOffset} />
            </div>
            <div
              className="absolute inset-0 pointer-events-none z-20"
              style={{ backgroundImage: 'linear-gradient(rgba(0,0,0,0) 50%, rgba(0,0,0,0.72) 50%)', backgroundSize: '100% 4px' }}
            />
            <div className="absolute inset-0 pointer-events-none z-20 shadow-[inset_0_0_8px_rgba(0,0,0,0.9)]" />
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ------------------------------------------------------------ voice input
type SpeechResultList = { length: number; [i: number]: { [j: number]: { transcript: string } } }
type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: { results: SpeechResultList }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
}
type SpeechCtor = new () => SpeechRecognitionLike

function speechRecognition(): SpeechCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

// ------------------------------------------------------------------ input
export type MascotSubmit = { prompt: string; provider: string; effort: Effort }

type Props = {
  onSubmit: (data: MascotSubmit) => void
  onCancel: () => void
  isProcessing: boolean
  providers: AgentProviders | null
  showWelcome: boolean
  title: string
  subtitle: string
  placeholder?: string
  /** A suggestion chip was clicked: send it with the current model and effort. */
  quickAsk?: { text: string; nonce: number } | null
  /** Which way the model menu opens: up when docked at the bottom, down on the start screen. */
  menuPlacement?: 'up' | 'down'
}

const EFFORT_KEY = 'campusai.effort'
const MODEL_KEY = 'campusai.model'

function remembered(key: string, fallback: string): string {
  try { return window.localStorage.getItem(key) ?? fallback } catch { return fallback }
}
function remember(key: string, value: string) {
  try { window.localStorage.setItem(key, value) } catch { /* private mode: not remembered */ }
}

export function MascotInput({
  onSubmit, onCancel, isProcessing, providers, showWelcome, title, subtitle,
  placeholder = 'Ask about attendance, classes, exams, hostel…', quickAsk, menuPlacement = 'up',
}: Props) {
  const [prompt, setPrompt] = useState('')
  const [modelId, setModelId] = useState(() => remembered(MODEL_KEY, ''))
  const [effort, setEffort] = useState<Effort>(() => remembered(EFFORT_KEY, 'medium') as Effort)
  const [menuOpen, setMenuOpen] = useState(false)
  const [isListening, setIsListening] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const listeningRef = useRef(false)
  const basePromptRef = useRef('')
  const voiceSupported = speechRecognition() !== null

  const options = modelOptions(providers)
  const selected = options.find(o => o.id === modelId && o.available) ?? options[0]
  const level = LEVELS.find(l => l.id === effort) ?? LEVELS[1]

  // Latest choices, for sending a suggestion chip from an effect.
  const choiceRef = useRef({ provider: selected.id, effort })
  useEffect(() => { choiceRef.current = { provider: selected.id, effort } }, [selected.id, effort])

  useEffect(() => {
    if (quickAsk) onSubmit({ prompt: quickAsk.text, ...choiceRef.current })
    // Only when a new chip is clicked, not when onSubmit's identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quickAsk])

  // Grow with the text, up to a limit.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.max(54, Math.min(el.scrollHeight, 260))}px`
  }, [prompt])

  useEffect(() => {
    if (!menuOpen) return
    const close = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menuOpen])

  const stopListening = () => {
    listeningRef.current = false
    setIsListening(false)
    try { recognitionRef.current?.stop() } catch { /* already stopped */ }
    recognitionRef.current = null
  }

  useEffect(() => () => stopListening(), [])

  const startListening = () => {
    const Ctor = speechRecognition()
    if (!Ctor) return
    basePromptRef.current = prompt ? prompt.trim() + ' ' : ''
    const recognition = new Ctor()
    recognition.continuous = true
    recognition.interimResults = true
    recognition.lang = navigator.language || 'en-IN'
    recognition.onresult = event => {
      let transcript = ''
      for (let i = 0; i < event.results.length; i++) transcript += event.results[i]?.[0]?.transcript ?? ''
      if (transcript) setPrompt(basePromptRef.current + transcript)
    }
    recognition.onerror = event => { if (event.error !== 'no-speech') stopListening() }
    recognition.onend = () => {
      // Chrome ends a session after a pause; keep going until the user stops.
      if (listeningRef.current) {
        try { recognition.start() } catch { stopListening() }
      }
    }
    recognitionRef.current = recognition
    listeningRef.current = true
    setIsListening(true)
    try { recognition.start() } catch { stopListening() }
  }

  const send = () => {
    const text = prompt.trim()
    if (!text || isProcessing) return
    stopListening()
    setPrompt('')
    onSubmit({ prompt: text, provider: selected.id, effort })
  }

  const isTyping = prompt.length > 0 || isListening || isProcessing
  const emotion: Emotion = isProcessing ? 'thinking' : 'reading'

  return (
    <div className="relative w-full flex flex-col items-center">
      <AnimatePresence>
        {showWelcome && !isTyping && (
          <motion.div
            key="welcome"
            initial={{ opacity: 0, y: -6, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -6, height: 0, transition: { duration: 0.22 } }}
            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
            className="mb-4 flex flex-col sm:flex-row items-center justify-center sm:justify-start gap-3.5 sm:gap-4.5 text-center sm:text-left select-none w-full"
          >
            <motion.div layoutId="robot-mascot" className="shrink-0">
              <RobotMascot emotion="reading" isListening={isListening} />
            </motion.div>
            <div>
              <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-zinc-950 dark:text-white">{title}</h2>
              <p className="text-xs sm:text-sm text-zinc-600 dark:text-zinc-400 font-medium mt-0.5">{subtitle}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        className="relative w-full"
        animate={{ paddingTop: isTyping ? 72 : 0 }}
        transition={{ type: 'spring', stiffness: 320, damping: 26 }}
      >
        {isTyping && (
          <motion.div
            layoutId="robot-mascot"
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}
            className="absolute top-1 right-4 sm:right-6 z-20 pointer-events-none"
          >
            <RobotMascot emotion={emotion} textLength={prompt.length} isListening={isListening} />
          </motion.div>
        )}

        <div className="relative z-10 w-full p-4 sm:p-5 rounded-3xl bg-white dark:bg-zinc-900 border border-zinc-200/90 dark:border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.06)] dark:shadow-[0_25px_60px_rgba(0,0,0,0.5)] transition-all duration-300 focus-within:border-zinc-400 dark:focus-within:border-white/25">
          <textarea
            ref={textareaRef}
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder={isListening ? 'Listening… speak your question' : isProcessing ? 'Thinking…' : placeholder}
            aria-label="Ask CampusAI"
            autoFocus
            className="w-full bg-transparent resize-none outline-hidden focus:outline-none font-medium text-base text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 dark:placeholder:text-zinc-500 leading-relaxed max-h-64 overflow-y-auto transition-[height] duration-150"
            style={{ minHeight: '54px' }}
          />

          <div className="flex flex-wrap sm:flex-nowrap items-center justify-between pt-3 border-t border-zinc-200/70 dark:border-white/5 gap-2 min-w-0">
            <div ref={menuRef} className="relative shrink-0">
              <button
                type="button"
                onClick={() => setMenuOpen(open => !open)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-zinc-100 dark:bg-white/5 hover:bg-zinc-200/70 dark:hover:bg-white/10 text-xs font-semibold text-zinc-900 dark:text-zinc-100 transition-all cursor-pointer whitespace-nowrap"
              >
                <selected.icon size={14} className={`${selected.color} shrink-0`} />
                <span className="truncate max-w-32.5">{selected.name}</span>
                <span className="px-1.5 py-0.5 rounded-md text-[9px] font-mono uppercase font-bold tracking-wider bg-zinc-200/70 dark:bg-white/10 text-zinc-700 dark:text-zinc-300">
                  {level.label}
                </span>
                <PiCaretDownBold size={11} className={`text-zinc-500 dark:text-zinc-400 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
              </button>

              <AnimatePresence>
                {menuOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: menuPlacement === 'up' ? 8 : -8, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: menuPlacement === 'up' ? 8 : -8, scale: 0.95 }}
                    transition={{ duration: 0.15 }}
                    className={`absolute ${menuPlacement === 'up' ? 'bottom-full mb-2' : 'top-full mt-2'} left-0 z-30 w-72 sm:w-80 p-2.5 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-white/10 shadow-[0_15px_40px_rgba(0,0,0,0.12)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.6)]`}
                  >
                    <div className="px-2 py-1 text-[10px] font-mono uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-bold">Model</div>
                    <div className="space-y-0.5">
                      {options.map(option => {
                        const isSelected = option.id === selected.id
                        return (
                          <button
                            key={option.id || 'auto'}
                            type="button"
                            disabled={!option.available}
                            onClick={() => { setModelId(option.id); remember(MODEL_KEY, option.id) }}
                            className={`w-full flex items-center justify-between p-2 rounded-xl text-xs font-medium transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                              isSelected
                                ? 'bg-zinc-100 dark:bg-white/10 text-zinc-950 dark:text-white font-semibold'
                                : 'hover:bg-zinc-100/70 dark:hover:bg-white/5 text-zinc-700 dark:text-zinc-300'
                            }`}
                          >
                            <span className="flex items-center gap-2.5 min-w-0">
                              <option.icon size={16} className={`${option.color} shrink-0`} />
                              <span className="text-left min-w-0">
                                <span className="block font-semibold leading-tight">{option.name}</span>
                                <span className="block text-[10px] text-zinc-500 dark:text-zinc-400 font-mono truncate">{option.detail}</span>
                              </span>
                            </span>
                            {isSelected && <PiCheckBold size={13} className="text-emerald-500 shrink-0" />}
                          </button>
                        )
                      })}
                    </div>

                    <div className="mt-2.5 pt-2.5 border-t border-zinc-200 dark:border-white/10">
                      <div className="px-2 pb-1.5 flex items-center justify-between">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-bold">Reasoning effort</span>
                        <span className="text-[10px] font-mono uppercase font-bold text-zinc-800 dark:text-zinc-200">{level.label}</span>
                      </div>
                      <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-zinc-100 dark:bg-white/5">
                        {LEVELS.map(item => (
                          <button
                            key={item.id}
                            type="button"
                            onClick={() => { setEffort(item.id); remember(EFFORT_KEY, item.id) }}
                            className={`py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                              item.id === effort
                                ? 'bg-white dark:bg-zinc-800 text-zinc-950 dark:text-white shadow-xs border border-zinc-200 dark:border-white/10'
                                : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-200/50 dark:hover:bg-white/5'
                            }`}
                          >
                            {item.label}
                          </button>
                        ))}
                      </div>
                      <div className="px-2 pt-1.5 text-[10px] text-zinc-600 dark:text-zinc-400 leading-tight">{level.desc}</div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <AnimatePresence>
                {isListening && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.85, x: 6 }}
                    animate={{ opacity: 1, scale: 1, x: 0 }}
                    exit={{ opacity: 0, scale: 0.85, x: 6 }}
                    transition={{ duration: 0.18 }}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-red-500/10 border border-red-500/25 shadow-[0_0_12px_rgba(239,68,68,0.25)] h-8"
                    title="Listening"
                  >
                    {[
                      { min: 4, max: 13, duration: 0.45 },
                      { min: 6, max: 18, duration: 0.55 },
                      { min: 8, max: 22, duration: 0.38 },
                      { min: 5, max: 16, duration: 0.5 },
                      { min: 4, max: 11, duration: 0.42 },
                    ].map((bar, i) => (
                      <motion.span
                        key={i}
                        className="w-1 bg-red-500 rounded-full"
                        animate={{ height: [`${bar.min}px`, `${bar.max}px`, `${bar.min}px`], opacity: [0.7, 1, 0.7] }}
                        transition={{ duration: bar.duration, repeat: Infinity, ease: 'easeInOut', delay: i * 0.08 }}
                      />
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>

              {voiceSupported && (
                <button
                  type="button"
                  onClick={() => (isListening ? stopListening() : startListening())}
                  disabled={isProcessing}
                  title={isListening ? 'Stop voice input' : 'Speak your question'}
                  aria-label={isListening ? 'Stop voice input' : 'Speak your question'}
                  className={`p-2 rounded-xl transition-all duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                    isListening
                      ? 'bg-red-500 text-white animate-pulse shadow-[0_0_12px_rgba(239,68,68,0.5)]'
                      : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-950 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-white/5'
                  }`}
                >
                  {isListening ? <PiMicrophoneFill size={16} /> : <PiMicrophoneBold size={16} />}
                </button>
              )}

              <button
                type="button"
                onClick={isProcessing ? onCancel : send}
                disabled={!isProcessing && !prompt.trim()}
                title={isProcessing ? 'Stop waiting for this answer' : 'Send'}
                aria-label={isProcessing ? 'Stop waiting for this answer' : 'Send'}
                className={`group w-9 h-9 rounded-full flex items-center justify-center transition-all duration-200 cursor-pointer ${
                  isProcessing
                    ? 'bg-amber-400/20 dark:bg-amber-500/25 border border-amber-500/40 text-amber-500 hover:scale-105 active:scale-95 shadow-[0_0_14px_rgba(245,158,11,0.3)]'
                    : prompt.trim()
                      ? 'bg-zinc-950 text-white dark:bg-white dark:text-zinc-950 hover:scale-105 active:scale-95 shadow-sm'
                      : 'bg-zinc-200/60 dark:bg-white/5 text-zinc-400 dark:text-zinc-600 cursor-not-allowed'
                }`}
              >
                {isProcessing ? <PiStopFill size={14} /> : <PiArrowUpBold size={16} />}
              </button>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  )
}
