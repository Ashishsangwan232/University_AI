const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/$/, '')

export type StudentProfile = {
  id: string
  name: string
  /** Everything below is optional: UMS is the source of truth and it does not
   *  publish a programme or a year, so a field it cannot supply is absent
   *  rather than invented. */
  program?: string | null
  department?: string | null
  year?: number | null
  semester?: number | null
  /** Registration number as UMS prints it. */
  student_id?: string | null
  section?: string | null
  term?: string | null
  hostel?: string | null
  room?: string | null
  portal_connected: boolean
  /** True when this identity came from the authenticated UMS session. */
  live?: boolean
  source?: string
  name_source?: string | null
}

export type AttendanceSubject = {
  name: string
  short: string
  attended: number
  total: number
  teacher: string
}

export type AttendanceResponse = {
  overall_percentage: number
  subjects: AttendanceSubject[]
  source: string
  /** True only when the numbers came from the authenticated UMS browser. */
  live: boolean
  state: string | null
  source_url: string | null
  updated_at: number | null
}

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

export type UMSLink = { text: string; href: string }
export type UMSAttachment = { name: string; href: string }

export type AnnouncementItem = {
  id: number
  title: string
  /** Exactly what UMS printed. */
  date: string
  /** The same stamp after the backend parsed it: "05 Sep 2026 10:30". */
  when?: string
  /** ISO date, or null when the stamp could not be read - never a guess. */
  date_iso?: string | null
  /** "10:30" when the stamp carried a time, otherwise empty. */
  time?: string
  reference: string
  channel: string
  tag: string
  text: string
  important: boolean
  attachments: UMSAttachment[]
  links: UMSLink[]
}

export type AnnouncementsResponse = {
  announcements: AnnouncementItem[]
  source: string
  live: boolean
  updated_at: number | null
}

export type MessageItem = {
  id: number
  title: string
  sender: string
  date: string
  when?: string
  date_iso?: string | null
  time?: string
  text: string
  attachments: UMSAttachment[]
  links: UMSLink[]
}

export type MessagesResponse = {
  messages: MessageItem[]
  source: string
  live: boolean
  updated_at: number | null
}

export type TimetableClass = {
  id: number
  day: string
  time: string
  end: string
  subject: string
  room: string
  type: string
  group: string
  teacher: string
}

export type TimetableResponse = {
  classes: TimetableClass[]
  source: string
  live: boolean
  updated_at: number | null
}

export type LeaveBalance = { total?: number; availed?: number; balance?: number }

export type LeaveResponse = {
  available: boolean
  /** Always true: CampusAI reads this page and never submits it. */
  read_only: boolean
  source: string
  balances: Record<string, LeaveBalance>
  profile: Record<string, string>
  leave_types: string[]
  terms: string[]
  controls_present: string[]
  updated_at: number | null
}

export type LeaveDraftInput = {
  leave_type: string
  start: string
  end: string
  visit_place: string
  reason: string
}

export type LeaveDraftResult = {
  ok: boolean
  errors: string[]
  warnings: string[]
  draft: LeaveDraftInput
  computed: {
    kind?: string
    units?: number
    unit_name?: string
    hours?: number
    available_before?: number | null
    available_after?: number | null
  }
  summary: string
  /** Always false. CampusAI has no path that submits a leave application. */
  can_submit_from_campusai: boolean
  next_step: string
  leave_types: string[]
}

export type LeavePrefillResult = {
  /** Always false: the form is filled, never sent. */
  submitted: boolean
  acknowledgement_ticked: boolean
  filled: { field: string; label: string; value: string }[]
  refused: { field: string; label: string; reason: string }[]
  form_now: Record<string, string>
  next_step: string
}

export type ClassEntry = {
  date: string
  time: string
  type: string
  status: string
  teacher: string
  reason: string
}

export type CourseDetail = {
  code: string
  entries: ClassEntry[]
  present: number
  absent: number
  recorded: number
}

export type AttendanceDetailResponse = {
  available: boolean
  source: string
  count: number
  courses: Record<string, CourseDetail>
  updated_at: number | null
}

export type AttendanceCalculateResponse = {
  current_percentage: number
  target_percentage: number
  can_miss: number
  must_attend: number
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

export function getStudent(): Promise<StudentProfile> {
  return request<StudentProfile>('/api/student')
}

export function getAttendance(): Promise<AttendanceResponse> {
  return request<AttendanceResponse>('/api/attendance')
}

export function calculateAttendance(attended: number, total: number, targetPercentage: number): Promise<AttendanceCalculateResponse> {
  return request<AttendanceCalculateResponse>('/api/attendance/calculate', {
    method: 'POST',
    body: JSON.stringify({ attended, total, target_percentage: targetPercentage }),
  })
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

export type KnowledgeStatus = {
  chunks: number
  pages: number
  sites: string[]
  has_vectors: boolean
  numpy_available: boolean
  updated_at: number | null
  location: string
  default_site: string
  embeddings: { provider: string; model: string; available: boolean; base_url: string }
}

export function getKnowledgeStatus(): Promise<KnowledgeStatus> {
  return request<KnowledgeStatus>('/api/rag/status')
}

export function getAgentProviders(): Promise<AgentProviders> {
  return request<AgentProviders>('/api/agent/providers')
}

export function getAnnouncements(): Promise<AnnouncementsResponse> {
  return request<AnnouncementsResponse>('/api/announcements')
}

export function getTimetable(): Promise<TimetableResponse> {
  return request<TimetableResponse>('/api/timetable')
}

export function getLeave(): Promise<LeaveResponse> {
  return request<LeaveResponse>('/api/ums/leave')
}

export function draftLeave(draft: LeaveDraftInput): Promise<LeaveDraftResult> {
  return request<LeaveDraftResult>('/api/leave/draft', {
    method: 'POST',
    body: JSON.stringify(draft),
  })
}

/** Types the draft into the real UMS form. Never ticks or submits. */
export function prefillLeave(draft: LeaveDraftInput): Promise<LeavePrefillResult> {
  return request<LeavePrefillResult>('/api/ums/leave/prefill', {
    method: 'POST',
    body: JSON.stringify(draft),
  })
}

export function getMessages(): Promise<MessagesResponse> {
  return request<MessagesResponse>('/api/messages')
}

export function getAttendanceDetail(force = false): Promise<AttendanceDetailResponse> {
  return request<AttendanceDetailResponse>(`/api/ums/attendance/detail${force ? '?force=true' : ''}`)
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
