import type { UMSPrefetch, UMSSessionStatus } from '../../api/campusApi'

type Props = {
  status: UMSSessionStatus | null
  busy: boolean
  onConnect: () => void
  onRefresh: () => void
  onDisconnect: () => void
}

const ITEM_LABELS: Record<string, string> = {
  attendance: 'attendance',
  profile: 'profile',
  timetable: 'timetable',
  announcements: 'notices',
  messages: 'messages',
  leave: 'hostel leave',
  attendance_detail: 'class-by-class attendance',
}

/** Still reading: some item is missing and hasn't just failed. */
function stillLoading(prefetch: UMSPrefetch | undefined): boolean {
  if (!prefetch?.enabled) return false
  return Object.values(prefetch.items).some(item => !item.ready && !item.error)
}

/** One line saying whether the bot can read the student's UMS data right now. */
export function UMSBar({ status, busy, onConnect, onRefresh, onDisconnect }: Props) {
  const connected = Boolean(status?.browser_connected && status?.authenticated)
  const waiting = Boolean(status?.running && !connected)
  const prefetch = status?.prefetch
  const loading = connected && stillLoading(prefetch)
  const failed = prefetch ? Object.entries(prefetch.items).filter(([, item]) => !item.ready && item.error) : []

  const tone = connected ? (loading ? 'wait' : 'ok') : waiting ? 'wait' : 'off'
  const label = connected
    ? loading
      ? `UMS connected — getting your data ready (${prefetch?.ready_count ?? 0}/${prefetch?.total ?? 0})`
      : 'UMS connected — your data is ready'
    : waiting
      ? status?.verification_required
        ? 'Finish the verification in the UMS window'
        : 'Sign in to UMS in the window that opened'
      : 'UMS not connected'
  const hint = connected
    ? loading
      ? `Reading ${ITEM_LABELS[prefetch?.current ?? ''] ?? 'your data'}… You can already ask; answers get faster as it arrives.`
      : failed.length
        ? `Couldn't read ${failed.map(([kind]) => ITEM_LABELS[kind] ?? kind).join(', ')} yet — will retry.`
        : 'Answers about your attendance, classes, notices, messages and leave are instant.'
    : 'University questions work now. Connect UMS for your own data.'

  return (
    <div className={`ums-bar ${tone}`} title={status?.last_error || status?.message || ''}>
      <span className="ums-dot" aria-hidden="true" />
      <div className="ums-text">
        <strong>{label}</strong>
        <span>{hint}</span>
      </div>
      {connected ? (
        <>
          <button className="ghost-btn" onClick={onRefresh} disabled={busy}>Refresh</button>
          <button className="ghost-btn" onClick={onDisconnect} disabled={busy}>Disconnect</button>
        </>
      ) : (
        <button className="primary-btn" onClick={onConnect} disabled={busy}>
          {busy ? 'Opening…' : waiting ? 'Show UMS window' : 'Connect UMS'}
        </button>
      )}
      {loading && prefetch && (
        <div className="ums-progress" aria-hidden="true">
          <span style={{ width: `${(100 * prefetch.ready_count) / Math.max(prefetch.total, 1)}%` }} />
        </div>
      )}
    </div>
  )
}
