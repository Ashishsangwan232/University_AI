// Chat input bar with the robot mascot riding on top. Icons come from
// lucide-react (UI) and react-icons (model logos); see AnimatedIcon for motion.
import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowUp, Check, ChevronDown, Languages, Mic, MicOff, Sparkles, Square } from 'lucide-react'
import { RiGeminiFill, RiOpenaiFill } from 'react-icons/ri'
import { SiOllama } from 'react-icons/si'
import type { AgentProviders } from '../../api/campusApi'
import { AnimatedIcon } from '../ui/AnimatedIcon'
import { iconButtonMotion } from '../ui/iconMotion'
import { LANGUAGES } from './languages'
import { RobotMascot, type Emotion } from './RobotMascot'

export { RobotMascot }

type IconProps = { size?: number; className?: string }

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

const LOGOS: Record<string, { icon: React.ComponentType<IconProps>; color: string }> = {
  ollama: { icon: SiOllama, color: 'text-zinc-700 dark:text-zinc-200' },
  gemini: { icon: RiGeminiFill, color: 'text-blue-500' },
  openai: { icon: RiOpenaiFill, color: 'text-zinc-700 dark:text-zinc-200' },
}

function modelOptions(providers: AgentProviders | null): ModelOption[] {
  const auto: ModelOption = {
    id: '',
    name: 'Auto',
    detail: providers
      ? `Uses ${providers.providers.find(p => p.id === providers.default)?.label ?? providers.default}, falls back if it fails`
      : 'Backend default',
    available: true,
    icon: Sparkles,
    color: 'text-emerald-500',
  }
  return [auto, ...(providers?.providers ?? []).map(p => ({
    id: p.id,
    name: p.label,
    detail: p.available ? p.model : `Unavailable: ${p.reason || 'no API key'}`,
    available: p.available,
    icon: LOGOS[p.id]?.icon ?? Sparkles,
    color: LOGOS[p.id]?.color ?? 'text-emerald-500',
  }))]
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
type Props = {
  onSubmit: (prompt: string) => void
  onCancel: () => void
  isProcessing: boolean
  providers: AgentProviders | null
  /** Chosen model ('' = Auto), effort and reply language - held by the app so
   *  that suggestion buttons send with the same choices. */
  provider: string
  effort: Effort
  language: string
  onProviderChange: (id: string) => void
  onEffortChange: (effort: Effort) => void
  onLanguageChange: (language: string) => void
  placeholder?: string
  /** Which way the menu opens: up when docked at the bottom, down on the start screen. */
  menuPlacement?: 'up' | 'down'
}

export function MascotInput({
  onSubmit, onCancel, isProcessing, providers, provider, effort, language,
  onProviderChange, onEffortChange, onLanguageChange,
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
  const lang = LANGUAGES.find(l => l.id === language) ?? LANGUAGES[0]

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
    // Listen in the chosen reply language; Auto uses the browser's language.
    recognition.lang = lang.speech || navigator.language || 'en-IN'
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
          <motion.button
            {...iconButtonMotion}
            type="button"
            onClick={() => setMenuOpen(open => !open)}
            title="Model, reasoning effort and reply language"
            className="flex items-center gap-1.5 h-10 px-3 rounded-full text-sm font-medium text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-white/10 transition-colors cursor-pointer whitespace-nowrap"
          >
            <AnimatedIcon icon={selected.icon} size={16} motion="pop" className={selected.color} />
            <span className="hidden sm:inline">{selected.name}</span>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider px-1.5 py-0.5 rounded-md bg-zinc-100 dark:bg-white/10 text-zinc-600 dark:text-zinc-300">
              {level.label}
            </span>
            {lang.id && (
              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                {lang.native.length <= 8 ? lang.native : lang.label}
              </span>
            )}
            <motion.span animate={{ rotate: menuOpen ? 180 : 0 }} style={{ display: 'inline-flex' }}>
              <ChevronDown size={13} className="text-zinc-500" />
            </motion.span>
          </motion.button>

          <AnimatePresence>
            {menuOpen && (
              <motion.div
                initial={{ opacity: 0, y: menuPlacement === 'up' ? 8 : -8, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: menuPlacement === 'up' ? 8 : -8, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className={`absolute ${menuPlacement === 'up' ? 'bottom-full mb-3' : 'top-full mt-3'} left-0 z-30 w-72 sm:w-80 max-h-[min(70vh,560px)] overflow-y-auto p-2 rounded-2xl bg-white dark:bg-[#2a2a2a] border border-zinc-200 dark:border-white/10 shadow-[0_15px_40px_rgba(0,0,0,0.15)] dark:shadow-[0_20px_50px_rgba(0,0,0,0.6)]`}
              >
                <div className="px-2 py-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">Model</div>
                {options.map(option => (
                  <motion.button
                    {...iconButtonMotion}
                    key={option.id || 'auto'}
                    type="button"
                    disabled={!option.available}
                    onClick={() => onProviderChange(option.id)}
                    className={`w-full flex items-center justify-between gap-2 p-2 rounded-xl text-sm transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
                      option.id === selected.id ? 'bg-zinc-100 dark:bg-white/10' : 'hover:bg-zinc-100/70 dark:hover:bg-white/5'
                    }`}
                  >
                    <span className="flex items-center gap-2.5 min-w-0">
                      <AnimatedIcon icon={option.icon} size={16} motion="pop" className={`${option.color} shrink-0`} />
                      <span className="text-left min-w-0">
                        <span className="block font-medium text-zinc-900 dark:text-zinc-100 leading-tight">{option.name}</span>
                        <span className="block text-[11px] text-zinc-500 dark:text-zinc-400 truncate">{option.detail}</span>
                      </span>
                    </span>
                    {option.id === selected.id && <Check size={15} className="text-zinc-900 dark:text-white shrink-0" />}
                  </motion.button>
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

                <div className="mt-2 pt-2 border-t border-zinc-200 dark:border-white/10">
                  <div className="px-2 pb-1.5 flex items-center gap-1.5 text-xs font-medium text-zinc-500 dark:text-zinc-400">
                    <Languages size={13} /> Reply language
                  </div>
                  <div className="grid grid-cols-2 gap-1">
                    {LANGUAGES.map(item => (
                      <button
                        key={item.id || 'auto'}
                        type="button"
                        onClick={() => onLanguageChange(item.id)}
                        className={`flex flex-col items-start px-2.5 py-1.5 rounded-lg text-left transition-colors cursor-pointer ${
                          item.id === lang.id ? 'bg-zinc-100 dark:bg-white/10' : 'hover:bg-zinc-100/70 dark:hover:bg-white/5'
                        }`}
                      >
                        <span className="text-xs font-semibold text-zinc-900 dark:text-zinc-100">{item.label}</span>
                        <span className="text-[10px] text-zinc-500 dark:text-zinc-400 truncate max-w-full">{item.native}</span>
                      </button>
                    ))}
                  </div>
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
          <motion.button
            {...iconButtonMotion}
            type="button"
            onClick={() => (isListening ? stopListening() : startListening())}
            disabled={isProcessing}
            title={isListening ? 'Stop voice input' : `Speak your question${lang.id ? ` (${lang.label})` : ''}`}
            aria-label={isListening ? 'Stop voice input' : 'Speak your question'}
            className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${
              isListening ? 'bg-red-500 text-white' : 'text-zinc-700 dark:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-white/10'
            }`}
          >
            <AnimatedIcon icon={isListening ? MicOff : Mic} size={18} motion="pop" />
          </motion.button>
        )}

        <motion.button
          {...iconButtonMotion}
          type="button"
          onClick={isProcessing ? onCancel : send}
          disabled={!isProcessing && !prompt.trim()}
          title={isProcessing ? 'Stop waiting for this answer' : 'Send'}
          aria-label={isProcessing ? 'Stop waiting for this answer' : 'Send'}
          className={`w-10 h-10 shrink-0 rounded-full flex items-center justify-center transition-colors cursor-pointer ${
            isProcessing || prompt.trim()
              ? 'bg-[#2f6fed] text-white hover:bg-[#2860d6]'
              : 'bg-zinc-200 dark:bg-white/10 text-zinc-400 dark:text-zinc-500 cursor-not-allowed'
          }`}
        >
          {isProcessing
            ? <AnimatedIcon icon={Square} size={13} motion="pop" className="fill-current" />
            : <AnimatedIcon icon={ArrowUp} size={18} motion="lift" strokeWidth={2.5} />}
        </motion.button>
      </div>
    </div>
  )
}
