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

const OpenAiIcon = ({ size = 16, className = '' }: IconProps) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" className={className}>
    <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z" />
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
  const iconFor = (id: string) => (id === 'gemini' ? GeminiIcon : id === 'ollama' ? SiOllama : id === 'openai' ? OpenAiIcon : PiSparkleFill)
  const colorFor = (id: string) => (id === 'gemini' ? 'text-blue-500' : id === 'ollama' || id === 'openai' ? 'text-zinc-700 dark:text-zinc-200' : 'text-emerald-500')
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
  onSubmit: (prompt: string) => void
  onCancel: () => void
  isProcessing: boolean
  providers: AgentProviders | null
  /** Chosen model ('' = Auto) and effort. Held by the app so that suggestion
   *  buttons can send with the same choice without going through this box. */
  provider: string
  effort: Effort
  onProviderChange: (id: string) => void
  onEffortChange: (effort: Effort) => void
  placeholder?: string
  /** Which way the model menu opens: up when docked at the bottom, down on the start screen. */
  menuPlacement?: 'up' | 'down'
}

export function MascotInput({
  onSubmit, onCancel, isProcessing, providers, provider, effort, onProviderChange, onEffortChange,
  placeholder = 'Ask CampusAI', menuPlacement = 'up',
}: Props) {
  const [prompt, setPrompt] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [isListening, setIsListening] = useState(false)

  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const listeningRef = useRef(false)
  const basePromptRef = useRef('')
  const voiceSupported = speechRecognition() !== null

  const options = modelOptions(providers)
  const selected = options.find(o => o.id === provider && o.available) ?? options[0]
  const level = LEVELS.find(l => l.id === effort) ?? LEVELS[1]

  // Grow with the text, up to a limit - and re-measure when the width changes.
  useEffect(() => {
    const fit = () => {
      const el = textareaRef.current
      if (!el) return
      el.style.height = 'auto'
      el.style.height = `${Math.max(24, Math.min(el.scrollHeight, 200))}px`
    }
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
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
    onSubmit(text)
  }

  const isTyping = prompt.length > 0 || isListening || isProcessing
  const emotion: Emotion = isProcessing ? 'thinking' : 'reading'

  return (
    <div className="relative w-full">
      {/* The robot rides on top of the bar while you type or it thinks. */}
      <AnimatePresence>
        {isTyping && (
          <motion.div
            key="rider"
            initial={{ opacity: 0, y: 12, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.9 }}
            transition={{ type: 'spring', stiffness: 320, damping: 26 }}
            className="absolute -top-[74px] right-6 z-20 pointer-events-none"
          >
            <RobotMascot emotion={emotion} textLength={prompt.length} isListening={isListening} />
          </motion.div>
        )}
      </AnimatePresence>

      <div className="relative z-10 flex items-end gap-1.5 w-full pl-2 pr-2 py-2 rounded-[28px] bg-white dark:bg-[#262626] border border-zinc-200 dark:border-transparent shadow-[0_4px_20px_rgba(0,0,0,0.06)] dark:shadow-none">
        <div ref={menuRef} className="relative shrink-0">
          <button
            type="button"
            onClick={() => setMenuOpen(open => !open)}
            title="Model and reasoning effort"
            className="flex items-center gap-1.5 h-10 px-3 rounded-full text-sm font-medium text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-white/10 transition-colors cursor-pointer whitespace-nowrap"
          >
            <selected.icon size={16} className={`${selected.color} shrink-0`} />
            <span className="hidden sm:inline">{selected.name}</span>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-md bg-zinc-100 dark:bg-white/10 text-zinc-600 dark:text-zinc-300">
              {level.label}
            </span>
            <PiCaretDownBold size={11} className={`text-zinc-500 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
          </button>

          <AnimatePresence>
            {menuOpen && (
              <motion.div
                initial={{ opacity: 0, y: menuPlacement === 'up' ? 8 : -8, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: menuPlacement === 'up' ? 8 : -8, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className={`absolute ${menuPlacement === 'up' ? 'bottom-full mb-3' : 'top-full mt-3'} left-0 z-30 w-72 sm:w-80 p-2 rounded-2xl bg-white dark:bg-[#2f2f2f] border border-zinc-200 dark:border-white/10 shadow-[0_15px_40px_rgba(0,0,0,0.15)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.6)]`}
              >
                <div className="px-2 py-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">Model</div>
                {options.map(option => (
                  <button
                    key={option.id || 'auto'}
                    type="button"
                    disabled={!option.available}
                    onClick={() => onProviderChange(option.id)}
                    className={`w-full flex items-center justify-between gap-2 p-2 rounded-xl text-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                      option.id === selected.id ? 'bg-zinc-100 dark:bg-white/10' : 'hover:bg-zinc-100/70 dark:hover:bg-white/5'
                    }`}
                  >
                    <span className="flex items-center gap-2.5 min-w-0">
                      <option.icon size={16} className={`${option.color} shrink-0`} />
                      <span className="text-left min-w-0">
                        <span className="block font-medium text-zinc-900 dark:text-zinc-100 leading-tight">{option.name}</span>
                        <span className="block text-[11px] text-zinc-500 dark:text-zinc-400 truncate">{option.detail}</span>
                      </span>
                    </span>
                    {option.id === selected.id && <PiCheckBold size={14} className="text-zinc-900 dark:text-white shrink-0" />}
                  </button>
                ))}

                <div className="mt-2 pt-2 border-t border-zinc-200 dark:border-white/10">
                  <div className="px-2 pb-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">Reasoning effort</div>
                  <div className="grid grid-cols-3 gap-1 p-1 rounded-xl bg-zinc-100 dark:bg-white/5">
                    {LEVELS.map(item => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => onEffortChange(item.id)}
                        className={`py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                          item.id === effort
                            ? 'bg-white dark:bg-zinc-700 text-zinc-950 dark:text-white shadow-xs'
                            : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white'
                        }`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                  <div className="px-2 pt-1.5 text-[11px] text-zinc-500 dark:text-zinc-400">{level.desc}</div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <textarea
          ref={textareaRef}
          value={prompt}
          rows={1}
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
          className="flex-1 min-w-0 self-center bg-transparent resize-none outline-none py-2 px-1 text-base text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-500 dark:placeholder:text-zinc-400 leading-6 max-h-[200px] overflow-y-auto"
        />

        <AnimatePresence>
          {isListening && (
            <motion.div
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.85 }}
              transition={{ duration: 0.18 }}
              className="self-center flex items-center gap-1 px-2 h-8 rounded-full bg-red-500/10"
              title="Listening"
            >
              {[
                { min: 4, max: 13, duration: 0.45 },
                { min: 6, max: 18, duration: 0.55 },
                { min: 8, max: 20, duration: 0.38 },
                { min: 5, max: 16, duration: 0.5 },
              ].map((bar, i) => (
                <motion.span
                  key={i}
                  className="w-1 bg-red-500 rounded-full"
                  animate={{ height: [`${bar.min}px`, `${bar.max}px`, `${bar.min}px`] }}
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
            className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
              isListening ? 'bg-red-500 text-white' : 'text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-white/10'
            }`}
          >
            {isListening ? <PiMicrophoneFill size={18} /> : <PiMicrophoneBold size={18} />}
          </button>
        )}

        <button
          type="button"
          onClick={isProcessing ? onCancel : send}
          disabled={!isProcessing && !prompt.trim()}
          title={isProcessing ? 'Stop waiting for this answer' : 'Send'}
          aria-label={isProcessing ? 'Stop waiting for this answer' : 'Send'}
          className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center transition-all cursor-pointer ${
            isProcessing || prompt.trim()
              ? 'bg-[#2f6fed] text-white hover:bg-[#2860d6] active:scale-95'
              : 'bg-zinc-200 dark:bg-white/10 text-zinc-400 dark:text-zinc-500 cursor-not-allowed'
          }`}
        >
          {isProcessing ? <PiStopFill size={14} /> : <PiArrowUpBold size={17} />}
        </button>
      </div>
    </div>
  )
}
