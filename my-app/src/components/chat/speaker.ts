// Reads text aloud with the free offline Piper voices on the backend (Hindi for
// Devanagari, English otherwise). Falls back to the browser's own voices when
// the backend voice is missing, and for scripts Piper has no voice for.
// Text is cut into sentence-sized chunks; the next chunk is made while the
// current one plays, so long answers start quickly and play without gaps.
import { getTtsStatus, ttsAudio } from '../../api/campusApi'
import { isHindiScript, speakable } from './speakable'
import { canSpeak, langFromText, pickVoice } from './speech'

type Chunk = { text: string; lang: 'hi' | 'en' | 'other' }
export type SpeakDone = 'ended' | 'stopped'
export type SpeakHandle = { stop: () => void }
type Options = {
  /** Browser language for fallback voices, e.g. "en-IN". */
  fallbackLang?: string
  onStart?: () => void
  onDone?: (reason: SpeakDone) => void
}

const MAX_CHUNK = 220
const LATIN_OR_DEVANAGARI = /^[\p{Script=Latin}\p{Script=Devanagari}\p{N}\p{P}\p{S}\s]*$/u

let piperCheck: Promise<boolean> | null = null
function piperAvailable(): Promise<boolean> {
  piperCheck ??= getTtsStatus().then(s => Boolean(s.available)).catch(() => false).then(ok => {
    if (!ok) window.setTimeout(() => { piperCheck = null }, 30_000) // backend may come up later
    return ok
  })
  return piperCheck
}

/** Sentence-sized chunks, each tagged with the voice that should read it. */
export function speechChunks(text: string): Chunk[] {
  const pieces: string[] = []
  for (const sentence of text.split(/(?<=[.!?।])\s+|\n+/).map(s => s.trim()).filter(Boolean)) {
    if (sentence.length <= MAX_CHUNK * 1.4) { pieces.push(sentence); continue }
    let current = ''
    for (const part of sentence.split(/(?<=[,;:])\s+/)) {
      if (current && current.length + part.length + 1 > MAX_CHUNK) { pieces.push(current); current = part }
      else current = current ? `${current} ${part}` : part
    }
    if (current) pieces.push(current)
  }
  const chunks: Chunk[] = []
  for (const piece of pieces) {
    const lang: Chunk['lang'] = !LATIN_OR_DEVANAGARI.test(piece) ? 'other' : isHindiScript(piece) ? 'hi' : 'en'
    const last = chunks[chunks.length - 1]
    if (last && last.lang === lang && last.text.length + piece.length < MAX_CHUNK) last.text += ` ${piece}`
    else chunks.push({ text: piece, lang })
  }
  return chunks
    .map(c => (c.lang === 'other' ? c : { ...c, text: speakable(c.text, c.lang) }))
    .filter(c => /[\p{L}\p{N}]/u.test(c.text))
}

let current: SpeakHandle | null = null

/** Start reading text aloud; any earlier reading stops first. */
export function speakAloud(text: string, options: Options = {}): SpeakHandle {
  current?.stop()
  const chunks = speechChunks(text)
  const controller = new AbortController()
  const urls: string[] = []
  let finished = false
  let usedBrowser = false
  let audio: HTMLAudioElement | null = null
  let wake: (() => void) | null = null // resolves whatever is playing, on stop

  const finish = (reason: SpeakDone) => {
    if (finished) return
    finished = true
    controller.abort()
    if (audio) { audio.pause(); audio.removeAttribute('src') }
    if (usedBrowser && canSpeak()) window.speechSynthesis.cancel()
    wake?.()
    urls.forEach(url => URL.revokeObjectURL(url))
    if (current === handle) current = null
    options.onDone?.(reason)
  }
  const handle: SpeakHandle = { stop: () => finish('stopped') }
  current = handle

  const fetchChunk = (chunk: Chunk) => {
    const pending = ttsAudio(chunk.text, controller.signal).then(blob => {
      const url = URL.createObjectURL(blob)
      urls.push(url)
      return url
    })
    pending.catch(() => {}) // handled where it is awaited
    return pending
  }

  const playUrl = (url: string) => new Promise<void>((resolve, reject) => {
    audio = new Audio(url)
    wake = resolve
    audio.onended = () => resolve()
    audio.onerror = () => reject(new Error('audio failed'))
    audio.play().catch(reject)
  })

  const speakBrowser = (chunk: Chunk) => new Promise<void>(resolve => {
    if (!canSpeak()) { resolve(); return }
    usedBrowser = true
    const fallback = options.fallbackLang || navigator.language || 'en-IN'
    const lang = chunk.lang === 'hi' ? 'hi-IN' : chunk.lang === 'other' ? langFromText(chunk.text, fallback) : (fallback.startsWith('en') ? fallback : 'en-IN')
    const utterance = new SpeechSynthesisUtterance(chunk.text)
    utterance.lang = lang
    const voice = pickVoice(lang)
    if (voice) utterance.voice = voice
    wake = resolve
    utterance.onend = () => resolve()
    utterance.onerror = () => resolve()
    window.speechSynthesis.speak(utterance)
  })

  const run = async () => {
    let piper = chunks.some(c => c.lang !== 'other') && await piperAvailable()
    const pending = new Map<number, Promise<string>>()
    const prefetch = (i: number) => {
      if (piper && i < chunks.length && chunks[i].lang !== 'other' && !pending.has(i)) pending.set(i, fetchChunk(chunks[i]))
    }
    prefetch(0)
    for (let i = 0; i < chunks.length; i++) {
      if (finished) return
      const chunk = chunks[i]
      if (i === 0) options.onStart?.()
      if (piper && chunk.lang !== 'other') {
        try {
          prefetch(i)
          const url = await pending.get(i)!
          if (finished) return
          prefetch(i + 1)
          await playUrl(url)
          continue
        } catch {
          if (finished) return
          piper = false // backend voice failed: browser voices for the rest
        }
      }
      prefetch(i + 1)
      await speakBrowser(chunk)
    }
    finish('ended')
  }
  if (!chunks.length) window.setTimeout(() => finish('ended'), 0)
  else void run()
  return handle
}
