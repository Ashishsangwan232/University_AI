export type Page =
  | 'dashboard' | 'chat' | 'attendance' | 'timetable' | 'announcements'
  | 'messages' | 'leave' | 'services' | 'profile'

export type Subject = { name: string; short: string; attended: number; total: number; teacher: string }
export type Announcement = { title: string; date: string; tag: string; text: string }
export type ClassItem = { time: string; end: string; subject: string; room: string; teacher: string; active: boolean }
export type ChatMessage = {
  role: 'user' | 'ai'
  text: string
  source?: string
  toolUsed?: string | null
  /** Which model wrote this answer, e.g. "Ollama Cloud (gpt-oss:120b)". */
  model?: string
  /** Set when the model that answered was not the one that was asked. */
  note?: string
}
