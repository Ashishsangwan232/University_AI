// Rewrites dates, money, numbers and codes into words a voice can say well.
// "26-10-2026" -> "26 October 2026" / "26 अक्टूबर 2026", "₹1,28,700" ->
// "1 lakh 28 thousand 700 rupees" / "1 लाख 28 हज़ार 700 रुपये",
// "39/42" -> "39 out of 42" / "42 में से 39", "97%" -> "97 percent" / "97 प्रतिशत".

export type SpeechLang = 'hi' | 'en'

export const isHindiScript = (text: string) => /[ऀ-ॿ]/.test(text)

const MONTHS = {
  en: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  hi: ['जनवरी', 'फ़रवरी', 'मार्च', 'अप्रैल', 'मई', 'जून', 'जुलाई', 'अगस्त', 'सितंबर', 'अक्टूबर', 'नवंबर', 'दिसंबर'],
}

const WORDS = {
  en: { crore: 'crore', lakh: 'lakh', thousand: 'thousand', rupees: 'rupees', percent: 'percent', point: 'point', to: 'to', and: 'and', then: 'then' },
  hi: { crore: 'करोड़', lakh: 'लाख', thousand: 'हज़ार', rupees: 'रुपये', percent: 'प्रतिशत', point: 'दशमलव', to: 'से', and: 'और', then: 'फिर' },
}

/** English letter names in Hindi, so "CSE" is said "सी एस ई" by the Hindi voice. */
const HINDI_LETTERS: Record<string, string> = {
  A: 'ए', B: 'बी', C: 'सी', D: 'डी', E: 'ई', F: 'एफ़', G: 'जी', H: 'एच', I: 'आई', J: 'जे', K: 'के', L: 'एल', M: 'एम',
  N: 'एन', O: 'ओ', P: 'पी', Q: 'क्यू', R: 'आर', S: 'एस', T: 'टी', U: 'यू', V: 'वी', W: 'डब्ल्यू', X: 'एक्स', Y: 'वाई', Z: 'ज़ेड',
}

/** 128700 -> "1 lakh 28 thousand 700" (Indian grouping, digits kept for the voice). */
function indianAmount(n: number, lang: SpeechLang): string {
  const w = WORDS[lang]
  const whole = Math.floor(n)
  const parts: string[] = []
  const crore = Math.floor(whole / 10_000_000)
  const lakh = Math.floor((whole % 10_000_000) / 100_000)
  const thousand = Math.floor((whole % 100_000) / 1000)
  const rest = whole % 1000
  if (crore) parts.push(`${crore} ${w.crore}`)
  if (lakh) parts.push(`${lakh} ${w.lakh}`)
  if (thousand) parts.push(`${thousand} ${w.thousand}`)
  if (rest || !parts.length) parts.push(String(rest))
  return parts.join(' ')
}

const decimal = (value: string, lang: SpeechLang) =>
  value.includes('.') ? value.replace('.', ` ${WORDS[lang].point} `) : value

export function speakable(text: string, lang: SpeechLang): string {
  const w = WORDS[lang]
  const month = (m: number) => MONTHS[lang][m - 1]
  let out = text

  // Units UMS prints that are noise when spoken.
  out = out.replace(/\(\s*L\s*,\s*T\s*,\s*P\s*\)/gi, '')

  // Dates: 26-10-2026, 26/10/2026, 2026-10-26.
  out = out.replace(/\b(\d{4})-(\d{1,2})-(\d{1,2})\b/g, (all, y, m, d) =>
    +m >= 1 && +m <= 12 ? `${+d} ${month(+m)} ${y}` : all)
  out = out.replace(/\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b/g, (all, d, m, y) =>
    +m >= 1 && +m <= 12 && +d >= 1 && +d <= 31 ? `${+d} ${month(+m)} ${y}` : all)

  // Phone numbers are said digit by digit, in small groups.
  out = out.replace(/(\+91[\s-]?)?\b(0\d{2,4})[\s-](\d{5,8})\b/g, (_a, _c, area: string, num: string) =>
    `${area.split('').join(' ')}, ${num.split('').join(' ')}`)
  out = out.replace(/(\+91[\s-]?)?\b([6-9]\d{4})\s?(\d{5})\b/g, (_a, _c, a: string, b: string) =>
    `${a.split('').join(' ')}, ${b.split('').join(' ')}`)

  // Money: ₹1,28,700 / Rs. 92,700 / INR 5000.
  out = out.replace(/(?:₹|\bRs\.?|\bINR)\s?([\d,]+(?:\.\d+)?)(\s*\/-)?/gi, (_a, num: string) =>
    `${indianAmount(Number(num.replace(/,/g, '')), lang)} ${w.rupees}`)
  // Other big numbers written with commas: 1,46,700 -> 1 lakh 46 thousand 700.
  out = out.replace(/\b\d{1,3}(?:,\d{2,3})+\b/g, num => indianAmount(Number(num.replace(/,/g, '')), lang))

  // Percentages: 97% / 92.9 % -> "97 percent", "92 point 9 percent".
  out = out.replace(/(\d+(?:\.\d+)?)\s?%/g, (_a, num: string) => `${decimal(num, lang)} ${w.percent}`)

  // Fractions such as attendance 39/42.
  out = out.replace(/\b(\d+)\s?\/\s?(\d+)\b/g, (_a, a: string, b: string) =>
    lang === 'hi' ? `${b} में से ${a}` : `${a} out of ${b}`)

  // Ranges: 14–30 December, 4–5 PM.
  out = out.replace(/\b(\d+)\s?[–—-]\s?(\d+)\b/g, `$1 ${w.to} $2`)

  // Times: 4:00 PM -> 4 PM, 11:59PM -> 11:59 PM.
  out = out.replace(/\b(\d{1,2}):00\s?(AM|PM)\b/gi, '$1 $2').replace(/\b(\d{1,2}:\d{2})(AM|PM)\b/gi, '$1 $2')

  // Course codes CSE408 -> CSE 408 (and letters spelt out for the Hindi voice).
  out = out.replace(/\b([A-Z]{2,5})(\d{2,4})\b/g, '$1 $2')
  if (lang === 'hi') {
    out = out.replace(/\b[A-Z]{2,5}\b/g, code => code.split('').map(ch => HINDI_LETTERS[ch] ?? ch).join(' '))
  }

  // Symbols.
  out = out.replace(/\s&\s/g, ` ${w.and} `).replace(/\s?[→⇒]\s?/g, `, ${w.then} `)
  return out.replace(/[ \t]+/g, ' ').trim()
}
