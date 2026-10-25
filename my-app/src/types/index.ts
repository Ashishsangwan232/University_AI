export type ChatMessage = {
  role: 'user' | 'ai'
  text: string
  source?: string
  toolUsed?: string | null
  /** Which model wrote this answer, e.g. "Ollama Cloud · gpt-oss:120b". */
  model?: string
  /** Set when the model that answered was not the one that was asked. */
  note?: string
}
