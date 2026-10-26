export interface Greeting {
  text: string
  language: string
}

export const GREETINGS: Greeting[] = [
  { text: 'Hello', language: 'English' },
  { text: 'नमस्ते', language: 'Hindi' },
  { text: 'ਸਤ ਸ੍ਰੀ ਅਕਾਲ', language: 'Punjabi' },
  { text: 'வணக்கம்', language: 'Tamil' },
  { text: 'నమస్కారం', language: 'Telugu' },
  { text: 'নমস্কার', language: 'Bengali' },
  { text: 'Bonjour', language: 'French' },
  { text: 'Hola', language: 'Spanish' },
  { text: 'こんにちは', language: 'Japanese' },
  { text: '안녕하세요', language: 'Korean' },
]
