// Hands-free voice mode: listen -> send after a short silence -> read the
// answer aloud -> listen again. Listening uses the browser's speech
// recognition (Hindi or English, your choice); answers are read by the free
// offline Piper voice (browser voices if it is missing). Questions and answers
// also go into the chat as usual.
import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Mic, MicOff, RotateCcw, Send, X } from 'lucide-react'
import type { ChatMessage } from '../../types'
import { AnimatedIcon } from '../ui/AnimatedIcon'
import { iconButtonMotion } from '../ui/iconMotion'
import { LoaderGooeyBlobs } from '../ui/LoaderGooeyBlobs'
import { RobotMascot } from './RobotMascot'
import { speakAloud, type SpeakHandle } from './speaker'
import {
  MIC_LANGS, saveMicLang, savedMicLang, speechRecognition, spokenText, transcriptOf,
  type MicLang, type SpeechRecognitionLike,
} from './speech'

type Phase = 'listening' | 'thinking' | 'speaking' | 'paused'

type Props = {
  open: boolean
  onClose: () => void
  /** voice=true asks for a short answer meant to be spoken. */
  ask: (prompt: string, voice?: boolean) => void
  thinking: boolean
  messages: ChatMessage[]
  /** Speech code for the reply language, e.g. "hi-IN"; '' = the browser's language. */
  speechLang: string
}

/** How long you can pause mid-question before it is sent. */
const SILENCE_MS = 2200

const STATUS: Record<Phase, string> = {
  listening: 'Listening…',
  thinking: 'Thinking…',
  speaking: 'Speaking…',
  paused: 'Tap the mic and ask your question',
}

/** Errors that will not fix themselves by listening again. */
const FATAL: Record<string, string> = {
  'not-allowed': 'Microphone access is blocked. Allow it in the browser to use voice mode.',
  'service-not-allowed': 'Microphone access is blocked. Allow it in the browser to use voice mode.',
  'audio-capture': 'No microphone was found. Plug one in and tap the mic.',
  network: 'Voice input needs internet: the browser turns speech into text online.',
  'language-not-supported': 'This browser cannot listen in that language. Try the other one.',
}

export function VoiceMode({ open, onClose, ask, thinking, messages, speechLang }: Props) {
  const [phase, setPhase] = useState<Phase>('paused')
  const [heard, setHeard] = useState('')
  const [notice, setNotice] = useState('')
  const [micLang, setMicLang] = useState<MicLang>(savedMicLang)
  const [tick, setTick] = useState(0) // restarts the "sending soon" bar

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const speakerRef = useRef<SpeakHandle | null>(null)
  const openRef = useRef(open)
  const micLangRef = useRef(micLang)
  const sentAtRef = useRef(0)       // message count when the question was sent
  const emptyTriesRef = useRef(0)
  const committedRef = useRef('')   // heard before the browser restarted listening
  const latestRef = useRef('')      // everything heard for this question so far
  const fatalRef = useRef('')
  const silenceRef = useRef<number | null>(null)
  // listen() and send() call each other through refs (timers, restarts).
  const listenRef = useRef<(keep?: boolean) => void>(() => {})
  const sendRef = useRef<() => void>(() => {})

  useEffect(() => { openRef.current = open }, [open])

  const clearSilence = () => {
    if (silenceRef.current !== null) window.clearTimeout(silenceRef.current)
    silenceRef.current = null
  }

  const stopRecognition = useCallback(() => {
    const recognition = recognitionRef.current
    recognitionRef.current = null
    if (recognition) {
      recognition.onend = null
      recognition.onresult = null
      try {
        if (recognition.abort) recognition.abort()
        else recognition.stop()
      } catch { /* already stopped */ }
    }
  }, [])

  const stopSpeaking = () => {
    speakerRef.current?.stop()
    speakerRef.current = null
  }

  const send = useCallback(() => {
    clearSilence()
    const text = latestRef.current.trim()
    stopRecognition()
    committedRef.current = ''
    latestRef.current = ''
    if (!text) return
    emptyTriesRef.current = 0
    sentAtRef.current = -1 // set once the question shows up in the chat
    setPhase('thinking')
    ask(text, true)
  }, [ask, stopRecognition])
  useEffect(() => { sendRef.current = send }, [send])

  /** Start listening. keep=true continues the same question after a restart. */
  const listen = useCallback((keep = false) => {
    const Ctor = speechRecognition()
    if (!Ctor) {
      setNotice('This browser cannot listen. Voice mode works in Chrome and Edge.')
      setPhase('paused')
      return
    }
    stopRecognition()
    stopSpeaking()
    if (!keep) {
      clearSilence()
      committedRef.current = ''
      latestRef.current = ''
      setHeard('')
      setNotice('')
    }
    fatalRef.current = ''
    const recognition = new Ctor()
    recognition.continuous = true    // keeps listening through pauses; we decide when you're done
    recognition.interimResults = true
    recognition.lang = micLangRef.current
    recognition.onresult = event => {
      const now = transcriptOf(event.results).text
      const full = [committedRef.current, now].filter(Boolean).join(' ')
      if (!full || full === latestRef.current) return
      latestRef.current = full
      setHeard(full)
      setNotice('')
      // Every new word restarts the silence countdown.
      clearSilence()
      setTick(t => t + 1)
      silenceRef.current = window.setTimeout(() => sendRef.current(), SILENCE_MS)
    }
    recognition.onerror = event => {
      if (FATAL[event.error]) fatalRef.current = FATAL[event.error]
    }
    recognition.onend = () => {
      if (!openRef.current || recognitionRef.current !== recognition) return
      recognitionRef.current = null
      if (fatalRef.current) {
        clearSilence()
        setNotice(fatalRef.current)
        setPhase('paused')
      } else if (latestRef.current) {
        // The browser stopped by itself mid-question: keep the words, keep listening.
        committedRef.current = latestRef.current
        listenRef.current(true)
      } else if (++emptyTriesRef.current < 3) {
        listenRef.current(true) // nothing heard yet: listen a little longer
      } else {
        emptyTriesRef.current = 0
        setNotice("Didn't hear anything. Tap the mic and ask again.")
        setPhase('paused')
      }
    }
    recognitionRef.current = recognition
    setPhase('listening')
    try { recognition.start() } catch { setPhase('paused') }
  }, [stopRecognition])
  useEffect(() => { listenRef.current = listen }, [listen])

  const speak = useCallback((text: string) => {
    if (!text) { if (openRef.current) listenRef.current(); return }
    setPhase('speaking')
    speakerRef.current = speakAloud(text, {
      fallbackLang: speechLang || 'en-IN',
      onDone: reason => {
        speakerRef.current = null
        if (reason === 'ended' && openRef.current) listenRef.current()
      },
    })
  }, [speechLang])

  const stopAll = useCallback(() => {
    clearSilence()
    stopRecognition()
    stopSpeaking()
  }, [stopRecognition])

  // Open: start listening. Close: stop everything.
  useEffect(() => {
    if (open) {
      emptyTriesRef.current = 0
      // Next tick, not inside this effect, so React does not re-render mid-effect.
      const id = window.setTimeout(() => listenRef.current(), 0)
      return () => window.clearTimeout(id)
    }
    stopAll()
  }, [open, stopAll])

  useEffect(() => stopAll, [stopAll])

  // Remember where the chat was when the question went in...
  useEffect(() => {
    if (phase === 'thinking' && sentAtRef.current === -1 && messages[messages.length - 1]?.role === 'user') {
      sentAtRef.current = messages.length
    }
  }, [messages, phase])

  // ...and read the answer aloud once it arrives.
  useEffect(() => {
    if (phase !== 'thinking' || thinking || sentAtRef.current <= 0) return
    const answer = messages.slice(sentAtRef.current).find(m => m.role === 'ai')
    if (answer) speak(spokenText(answer.text))
  }, [phase, thinking, messages, speak])

  const toggleMic = () => {
    if (phase === 'listening') { clearSilence(); stopRecognition(); setPhase('paused') }
    else if (phase === 'speaking' || phase === 'paused') listen()
  }

  const chooseMic = (lang: MicLang) => {
    if (lang === micLangRef.current) return
    micLangRef.current = lang
    setMicLang(lang)
    saveMicLang(lang)
    if (phase === 'listening' || phase === 'paused') listen()
  }

  const waiting = phase === 'listening' && heard.length > 0

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="voice-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          role="dialog"
          aria-label="Voice mode"
        >
          <div className="voice-langs" role="radiogroup" aria-label="Language you speak in">
            {MIC_LANGS.map(item => (
              <button
                key={item.id}
                role="radio"
                aria-checked={micLang === item.id}
                className={micLang === item.id ? 'active' : ''}
                onClick={() => chooseMic(item.id)}
                disabled={phase === 'thinking'}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="voice-stage">
            <button
              className="voice-robot"
              onClick={phase === 'speaking' ? () => listen() : undefined}
              title={phase === 'speaking' ? 'Stop and listen' : undefined}
              aria-label={phase === 'speaking' ? 'Stop speaking and listen' : 'Robot'}
              tabIndex={phase === 'speaking' ? 0 : -1}
            >
              {/* Rings pulse out while it listens or speaks. */}
              {(phase === 'listening' || phase === 'speaking') && [0, 1, 2].map(i => (
                <motion.span
                  key={`${phase}-${i}`}
                  className={`voice-ring ${phase}`}
                  initial={{ scale: 0.8, opacity: 0.5 }}
                  animate={{ scale: 2.1, opacity: 0 }}
                  transition={{ duration: 2.2, repeat: Infinity, delay: i * 0.7, ease: 'easeOut' }}
                />
              ))}
              <div style={{ transform: 'scale(1.7)' }}>
                <RobotMascot
                  emotion={phase === 'thinking' ? 'thinking' : 'reading'}
                  textLength={heard.length}
                  isListening={phase === 'listening'}
                />
              </div>
            </button>

            <div className="voice-status">
              {phase === 'thinking' && <LoaderGooeyBlobs size={8} color="var(--ok)" />}
              <span>{STATUS[phase]}</span>
            </div>
            <p className={`voice-heard ${heard ? '' : 'empty'}`}>
              {heard || (phase === 'listening'
                ? (micLang === 'hi-IN' ? 'पूछिए — attendance, classes, exams, hostel…' : 'Ask about attendance, classes, exams, hostel…')
                : ' ')}
            </p>

            <div className="voice-pending" aria-hidden={!waiting}>
              {waiting && (
                <>
                  <div className="voice-countdown">
                    <motion.span
                      key={tick}
                      initial={{ scaleX: 1 }}
                      animate={{ scaleX: 0 }}
                      transition={{ duration: SILENCE_MS / 1000, ease: 'linear' }}
                    />
                  </div>
                  <span className="voice-hint">Pause is fine — it sends when you stop talking</span>
                  <div className="voice-pending-actions">
                    <button onClick={() => listen()} title="Start the question again">
                      <RotateCcw size={14} /> Start over
                    </button>
                    <button className="primary" onClick={() => send()} title="Send now">
                      <Send size={14} /> Send now
                    </button>
                  </div>
                </>
              )}
              {phase === 'speaking' && <span className="voice-hint">Tap the robot or the mic to interrupt</span>}
            </div>
            {notice && <p className="voice-notice">{notice}</p>}
          </div>

          <div className="voice-controls">
            <motion.button
              {...iconButtonMotion}
              className={`voice-btn mic ${phase === 'listening' ? 'live' : ''}`}
              onClick={toggleMic}
              disabled={phase === 'thinking'}
              title={phase === 'listening' ? 'Pause listening' : 'Talk'}
              aria-label={phase === 'listening' ? 'Pause listening' : 'Talk'}
            >
              <AnimatedIcon icon={phase === 'listening' ? Mic : MicOff} size={24} motion="pop" />
            </motion.button>
            <motion.button {...iconButtonMotion} className="voice-btn close" onClick={onClose} title="End voice mode" aria-label="End voice mode">
              <AnimatedIcon icon={X} size={24} motion="spin" />
            </motion.button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
