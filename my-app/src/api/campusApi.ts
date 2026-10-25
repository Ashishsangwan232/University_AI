const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

/** Mirrors the backend UMS state machine exactly. */
export type UMSState =
  | 'IDLE'
  | 'BROWSER_STARTED'
  | 'AUTHENTICATION_PENDING'
  | 'AUTHENTICATED'
  | 'ATTENDANCE_NAVIGATION_STARTED'
  | 'ATTENDANCE_PAGE_FOUND'
  | 'ATTENDANCE_TABLE_FOUND'
  | 'ATTENDANCE_PARSED'
  | 'ATTENDANCE_VALIDATED'
  | 'ATTENDANCE_STORED'
  | 'READY'

export type UMSDiagnostics = {
  state: UMSState
  browser_started: boolean
  cdp_endpoint: string | null
  context_count: number
  page_count: number
  ums_page_count: number
  ums_page_urls: string[]
  ums_page_found: boolean
  authenticated: boolean
  verification_required: boolean
  login_page: boolean
  current_url: string | null
  current_title: string | null
  navigation_attempts: string[]
  attendance_page_found: boolean
  attendance_url: string | null
  frame_count: number
  frame_urls: string[]
  tables_scanned: number
  attendance_table_found: boolean
  table_headers: string[]
  table_sample_rows: string[]
  courses_parsed: number
  validated: boolean
  validation_error: string | null
  attendance_updated_at: number | null
  last_error: string | null
}

export type UMSSessionStatus = {
  state: UMSState
  running: boolean
  browser_connected: boolean
  authenticated: boolean
  verification_required: boolean
  login_page: boolean
  url: string | null
  title: string | null
  message: string
  attendance_captured: boolean
  attendance_course_count: number
  attendance_source_url: string | null
  attendance_updated_at: number | null
  last_error: string | null
  last_seen_at: number | null
  diagnostics: UMSDiagnostics
}

export type ApiError = Error & { status?: number; state?: string | null; diagnostics?: Partial<UMSDiagnostics> }

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
  })

  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    let state: string | null = null
    let diagnostics: Partial<UMSDiagnostics> | undefined
    try {
      const body = await response.json() as { detail?: unknown }
      // The UMS endpoints return a structured detail so the exact failure point
      // in the state machine is visible in the UI, not just an HTTP status.
      if (typeof body.detail === 'string') {
        detail = body.detail
      } else if (body.detail && typeof body.detail === 'object') {
        const shaped = body.detail as { message?: string; state?: string; diagnostics?: Partial<UMSDiagnostics> }
        detail = shaped.message ?? detail
        state = shaped.state ?? null
        diagnostics = shaped.diagnostics
      }
    } catch {
      // Keep the HTTP status as the useful error when there is no JSON body.
    }
    const error = new Error(detail) as ApiError
    error.status = response.status
    error.state = state
    error.diagnostics = diagnostics
    throw error
  }

  return response.json() as Promise<T>
}

export type AgentChatResponse = {
  answer: string
  intent: string
  tool_used: string | null
  source: string
  action: string | null
  /** Which model actually answered - not always the one that was asked. */
  provider: string
  provider_label: string
  model: string
  /** Models tried first that could not answer, with the reason. */
  fell_back_from: { provider: string; error: string }[]
  note: string
  /** The saved thread this answer belongs to. */
  conversation_id: string
  conversation_title: string
  /** How many earlier turns were sent with the question. */
  history_turns: number
}

export type Conversation = {
  id: string
  title: string
  message_count: number
  created_at: string
  updated_at: string
  has_summary?: boolean
}

export type ConversationMessage = {
  id: number
  role: string
  content: string
  tool_used: string
  source: string
  provider: string
  model: string
  created_at: string
}

export type ConversationDetail = Conversation & {
  summary: string
  messages: ConversationMessage[]
}

export type AgentProvider = {
  id: string
  label: string
  model: string
  available: boolean
  reason: string
}

export type AgentProviders = { default: string; providers: AgentProvider[] }

/**
 * Ask a question.
 *
 * `provider` overrides the backend's configured default. `conversationId`
 * continues a saved thread - the backend sends its earlier turns to the model,
 * so context does not have to be repeated. Omit it to start a new thread; the
 * reply carries the id to use from then on.
 */
export function askAgent(
  message: string, provider?: string, conversationId?: string,
): Promise<AgentChatResponse> {
  return request<AgentChatResponse>('/api/agent/chat', {
    method: 'POST',
    body: JSON.stringify({
      message,
      ...(provider ? { provider } : {}),
      ...(conversationId ? { conversation_id: conversationId } : {}),
    }),
  })
}

export function getConversations(): Promise<Conversation[]> {
  return request<Conversation[]>('/api/conversations')
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return request<ConversationDetail>(`/api/conversations/${id}`)
}

export function renameConversation(id: string, title: string): Promise<Conversation> {
  return request<Conversation>(`/api/conversations/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ title }),
  })
}

export function deleteConversation(id: string): Promise<{ deleted: string }> {
  return request<{ deleted: string }>(`/api/conversations/${id}`, { method: 'DELETE' })
}

export function getAgentProviders(): Promise<AgentProviders> {
  return request<AgentProviders>('/api/agent/providers')
}

export function startUMSSession(): Promise<UMSSessionStatus> {
  return request<UMSSessionStatus>('/api/ums/session/start', { method: 'POST' })
}

export function getUMSSessionStatus(): Promise<UMSSessionStatus> {
  return request<UMSSessionStatus>('/api/ums/session/status')
}

export function refreshUMS(): Promise<UMSSessionStatus> {
  return request<UMSSessionStatus>('/api/ums/session/refresh', { method: 'POST' })
}

export function stopUMSSession(): Promise<UMSSessionStatus> {
  return request<UMSSessionStatus>('/api/ums/session/stop', { method: 'POST' })
}

export function getUMSDiagnostics(): Promise<UMSDiagnostics> {
  return request<UMSDiagnostics>('/api/ums/diagnostics')
}

/** Plain-language description of where the UMS pipeline currently is. */
export function describeUMSState(status: UMSSessionStatus | null): string {
  if (!status || !status.running) return 'UMS browser not started'
  if (!status.browser_connected) return 'Browser open, Playwright not attached'
  if (status.verification_required) return 'Waiting for you to complete verification'
  if (status.login_page || !status.authenticated) return 'Waiting for manual UMS login'
  if (!status.attendance_captured) return 'Authenticated — locating the attendance table'
  return 'Live UMS attendance captured'
}
