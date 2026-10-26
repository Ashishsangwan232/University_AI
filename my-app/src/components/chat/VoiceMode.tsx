// Hands-free voice mode: listen -> send when you pause -> read the answer
// aloud -> listen again. Uses the browser's own speech recognition and
// speech synthesis. Questions and answers also go into the chat as usual.
import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Mic, MicOff, X } from 'lucide-react'
import type { ChatMessage } from '../../types'
import { AnimatedIcon } from '../ui/AnimatedIcon'
import { iconButtonMotion } from '../ui/iconMotion'
import { LoaderGooeyBlobs } from '../ui/LoaderGooeyBlobs'
import { RobotMascot } from './RobotMascot'
import { canSpeak, langFromText, pickVoice, speechRecognition, spokenText, transcriptOf, type SpeechRecognitionLike } from './speech'

type Phase = 'listening' | 'thinking' | 'speaking' | 'paused'

type Props = {
  open: boolean
  onClose: () => void
  ask: (prompt: string) => void
  thinking: boolean
  messages: ChatMessage[]
  /** Speech code for the reply language, e.g. "hi-IN"; '' = the browser's language. */
  speechLang: string
}

const STATUS: Record<Phase, string> = {
  listening: 'Listening…',
  thinking: 'Thinking…',
  speaking: 'Speaking…',
  paused: 'Tap the mic and ask your question',
}

export function VoiceMode({ open, onClose, ask, thinking, messages, speechLang }: Props) {
  const [phase, setPhase] = useState<Phase>('paused')
  const [heard, setHeard] = useState('')
  const [notice, setNotice] = useState('')
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const openRef = useRef(open)
  const sentAtRef = useRef(0)          // message count when the question was sent
  const emptyTriesRef = useRef(0)
  // listen() restarts itself (nothing heard yet); it does so through this ref.
  const listenRef = useRef<() => void>(() => {})
  const lang = speechLang || (typeof navigator !== 'undefined' ? navigator.language : '') || 'en-IN'

  useEffect(() => { openRef.current = open }, [open])

  const stopListening = useCallback(() => {
    const recognition = recognitionRef.current
    recognitionRef.current = null
    if (recognition) {
      recognition.onend = null
      try {
        if (recognition.abort) recognition.abort()
        else recognition.stop()
      } catch { /* already stopped */ }
    }
  }, [])

  const listen = useCallback(() => {
    const Ctor = speechRecognition()
    if (!Ctor) {
      setNotice('This browser cannot listen. Voice mode works in Chrome and Edge.')
      setPhase('paused')
      return
    }
    stopListening()
    if (canSpeak()) window.speechSynthesis.cancel()
    setHeard('')
    setNotice('')
    const recognition = new Ctor()
    recognition.continuous = false   // ends by itself when you pause
    recognition.interimResults = true
    recognition.lang = lang
    let latest = ''
    recognition.onresult = event => {
      latest = transcriptOf(event.results).text
      setHeard(latest)
    }
    recognition.onerror = event => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setNotice('Microphone access is blocked. Allow it in the browser to use voice mode.')
        setPhase('paused')
      }
    }
    recognition.onend = () => {
      if (!openRef.current || recognitionRef.current !== recognition) return
      recognitionRef.current = null
      if (latest) {
        emptyTriesRef.current = 0
        sentAtRef.current = -1 // set once the question shows up in the chat
        setPhase('thinking')
        ask(latest)
      } else if (++emptyTriesRef.current < 3) {
        listenRef.current() // nothing heard yet: keep listening a little longer
      } else {
        emptyTriesRef.current = 0
        setPhase('paused')
      }
    }
    recognitionRef.current = recognition
    setPhase('listening')
    try { recognition.start() } catch { setPhase('paused') }
  }, [ask, lang, stopListening])
  useEffect(() => { listenRef.current = listen }, [listen])

  const speak = useCallback((text: string) => {
    if (!canSpeak() || !text) { if (openRef.current) listen(); return }
    const voiceLang = langFromText(text, lang)
    const voice = pickVoice(voiceLang)
    // Speak sentence-sized pieces: Chrome stops long utterances after ~15 seconds.
    // Split after . ! ? । only when a space follows, so "90.7%" stays whole.
    const pieces = text.split(/(?<=[.!?।])\s+|\n+/).map(p => p.trim()).filter(Boolean)
    window.speechSynthesis.cancel()
    setPhase('speaking')
    pieces.forEach((piece, i) => {
      const utterance = new SpeechSynthesisUtterance(piece)
      utterance.lang = voiceLang
      if (voice) utterance.voice = voice
      if (i === pieces.length - 1) {
        utterance.onend = () => { if (openRef.current) listen() }
        utterance.onerror = () => { if (openRef.current) setPhase('paused') }
      }
      window.speechSynthesis.speak(utterance)
    })
  }, [lang, listen])

  // Open: start listening. Close: stop everything.
  useEffect(() => {
    if (open) {
      emptyTriesRef.current = 0
      // Next tick, not inside this effect, so React does not re-render mid-effect.
      const id = window.setTimeout(() => listen(), 0)
      return () => window.clearTimeout(id)
    } else {
      // Every opening starts fresh (listen() resets what was heard).
      stopListening()
      if (canSpeak()) window.speechSynthesis.cancel()
    }
    // Only when opening/closing; listen/stopListening are stable enough.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useEffect(() => () => { stopListening(); if (canSpeak()) window.speechSynthesis.cancel() }, [stopListening])

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
    if (phase === 'listening') { stopListening(); setPhase('paused') }
    else if (phase === 'speaking') { window.speechSynthesis.cancel(); listen() }
    else if (phase === 'paused') listen()
  }

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
          <div className="voice-stage">
            <div className="voice-robot">
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
            </div>

            <div className="voice-status">
              {phase === 'thinking' && <LoaderGooeyBlobs size={8} color="var(--ok)" />}
              <span>{STATUS[phase]}</span>
            </div>
            <p className={`voice-heard ${heard ? '' : 'empty'}`}>
              {heard || (phase === 'listening' ? 'Ask about attendance, classes, exams, hostel…' : ' ')}
            </p>
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
