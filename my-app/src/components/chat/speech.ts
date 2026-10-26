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

/** Joined transcript of every result so far, and whether the last one is final. */
export function transcriptOf(results: SpeechResultList): { text: string; final: boolean } {
  let text = ''
  let final = false
  for (let i = 0; i < results.length; i++) {
    text += results[i]?.[0]?.transcript ?? ''
    final = Boolean(results[i]?.isFinal)
  }
  return { text: text.trim(), final }
}

/**
 * An answer as something worth hearing: charts, diagrams, step blocks and
 * tables are left out (they stay on screen), links become their labels,
 * Markdown symbols go, and long answers stop after a few sentences.
 */
export function spokenText(markdown: string, maxChars = 650): string {
  let text = markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .split('\n')
    .filter(line => !/^\s*\|.*\|\s*$/.test(line))           // tables
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
