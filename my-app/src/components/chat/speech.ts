// Browser speech helpers shared by the mic button and voice mode.
// Both use the browser's built-in speech recognition and speech synthesis
// (Chrome and Edge support both); nothing is sent anywhere else.

type SpeechResultList = { length: number; [i: number]: { isFinal?: boolean; [j: number]: { transcript: string } } }
export type SpeechRecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  onresult: ((event: { results: SpeechResultList }) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
  start: () => void
  stop: () => void
  abort?: () => void
}
type SpeechCtor = new () => SpeechRecognitionLike

export function speechRecognition(): SpeechCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export const canSpeak = () => typeof window !== 'undefined' && 'speechSynthesis' in window

const comparable = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim()

/**
 * Joined transcript of every result so far, and whether the last one is final.
 * Some browsers (Edge) send a phrase again as a new piece that repeats or
 * extends the one before ("4 seater" then "4 seater 4"); that piece replaces
 * the earlier one instead of being added, so words are not doubled.
 */
export function transcriptOf(results: SpeechResultList): { text: string; final: boolean } {
  const pieces: string[] = []
  let final = false
  for (let i = 0; i < results.length; i++) {
    final = Boolean(results[i]?.isFinal)
    const piece = (results[i]?.[0]?.transcript ?? '').replace(/\s+/g, ' ').trim()
    if (!piece) continue
    const previous = pieces.length ? comparable(pieces[pieces.length - 1]) : ''
    const current = comparable(piece)
    if (previous && current.startsWith(previous)) pieces[pieces.length - 1] = piece // extends it
    else if (previous && previous.endsWith(current)) continue                       // repeats it
    else pieces.push(previous ? withoutOverlap(pieces[pieces.length - 1], piece) : piece)
  }
  return { text: pieces.filter(Boolean).join(' '), final }
}

/** "And 4 seater" + "4 seater 4" -> "4": drops the start of a piece that only
 *  repeats the last two or more words of the piece before it. */
function withoutOverlap(previous: string, piece: string): string {
  const before = previous.split(' ')
  const words = piece.split(' ')
  for (let size = Math.min(before.length, words.length); size >= 2; size--) {
    const tail = comparable(before.slice(-size).join(' '))
    if (tail && tail === comparable(words.slice(0, size).join(' '))) return words.slice(size).join(' ')
  }
  return piece
}

/** Language the mic listens in: Hindi (also catches Hinglish) or English. Remembered. */
export type MicLang = 'hi-IN' | 'en-IN'
export const MIC_LANGS: { id: MicLang; label: string }[] = [
  { id: 'hi-IN', label: 'हिंदी' },
  { id: 'en-IN', label: 'English' },
]
const MIC_KEY = 'campusai.micLang'

export function savedMicLang(): MicLang {
  try { return localStorage.getItem(MIC_KEY) === 'en-IN' ? 'en-IN' : 'hi-IN' } catch { return 'hi-IN' }
}

export function saveMicLang(lang: MicLang) {
  try { localStorage.setItem(MIC_KEY, lang) } catch { /* private window: not remembered */ }
}

const TABLE_ROW = /^\s*\|.*\|\s*$/
const TABLE_DIVIDER = /^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-*:?\s*\|?\s*$/

/** A table row said as a short sentence ("CSE408, 39/42, 93%."). The header
 *  row and the |---| divider are dropped; other lines pass through. */
function tableRowAsSentence(line: string, next: string | undefined): string {
  if (!TABLE_ROW.test(line)) return line
  if (TABLE_DIVIDER.test(line) || (next !== undefined && TABLE_DIVIDER.test(next))) return ''
  // Empty cells ("–", "-", "—") are skipped, not read out.
  const cells = line.split('|').map(cell => cell.trim()).filter(cell => cell && !/^[–—-]+$/.test(cell))
  return cells.length ? `${cells.join(', ')}.` : ''
}

/**
 * An answer as something worth hearing: charts, diagrams and step blocks are
 * left out (they stay on screen), table rows become short sentences, links
 * become their labels, Markdown symbols go, and long answers stop after a few
 * sentences.
 */
export function spokenText(markdown: string, maxChars = 650): string {
  let text = markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .split('\n')
    .map((line, i, lines) => tableRowAsSentence(line, lines[i + 1]))
    .filter(line => !/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) // dividers
    .filter(line => !/^[\s*_(>]*sources?\s*:/i.test(line))      // "Source: ..." lines (on screen)
    .join('\n')
    .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '$1')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/[*_`#>]+/g, '')
    .replace(/^\s*[-•]\s+/gm, '')
    .replace(/\(\s*\)/g, '')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{2,}/g, '\n')
    .trim()
  if (text.length > maxChars) {
    const cut = text.slice(0, maxChars)
    const end = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf('। '), cut.lastIndexOf('\n'))
    text = (end > maxChars * 0.5 ? cut.slice(0, end + 1) : cut) + ' The full answer is on screen.'
  }
  return text
}

/** A voice for a language like "hi-IN"; falls back to the same base language. */
export function pickVoice(lang: string): SpeechSynthesisVoice | null {
  if (!canSpeak() || !lang) return null
  const voices = window.speechSynthesis.getVoices()
  const base = lang.split('-')[0].toLowerCase()
  return (
    voices.find(v => v.lang.toLowerCase() === lang.toLowerCase()) ??
    voices.find(v => v.lang.toLowerCase().startsWith(base)) ??
    null
  )
}

/** Guess a speaking language from the text itself (script-based). */
export function langFromText(text: string, fallback: string): string {
  if (/[਀-੿]/.test(text)) return 'pa-IN'
  if (/[ऀ-ॿ]/.test(text)) return 'hi-IN'
  if (/[ঀ-৿]/.test(text)) return 'bn-IN'
  if (/[஀-௿]/.test(text)) return 'ta-IN'
  if (/[ఀ-౿]/.test(text)) return 'te-IN'
  if (/[઀-૿]/.test(text)) return 'gu-IN'
  if (/[؀-ۿ]/.test(text)) return 'ur-IN'
  return fallback
}
