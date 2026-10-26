import type { UMSPrefetch, UMSSessionStatus } from '../../api/campusApi'

type Props = {
  status: UMSSessionStatus | null
  backendDown: boolean
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
  attendance_detail: 'class log',
}

/** Still reading: some item is missing and hasn't just failed. */
function stillLoading(prefetch: UMSPrefetch | undefined): boolean {
  if (!prefetch?.enabled) return false
  return Object.values(prefetch.items).some(item => !item.ready && !item.error)
}

/** Compact UMS status for the sidebar: state, progress bar and actions. */
export function UMSBar({ status, backendDown, busy, onConnect, onRefresh, onDisconnect }: Props) {
  if (backendDown) {
    return (
      <div className="ums-card off">
        <div className="ums-line"><span className="ums-dot" /><strong>Backend not reachable</strong></div>
        <p className="ums-hint">Start it with: uvicorn app.main:app --reload</p>
      </div>
    )
  }

  const connected = Boolean(status?.browser_connected && status?.authenticated)
  const waiting = Boolean(status?.running && !connected)
  const prefetch = status?.prefetch
  const loading = connected && stillLoading(prefetch)
  const failed = prefetch ? Object.entries(prefetch.items).filter(([, item]) => !item.ready && item.error) : []

  const tone = connected ? (loading ? 'wait' : 'ok') : waiting ? 'wait' : 'off'
  const label = connected
    ? loading ? `UMS · loading ${prefetch?.ready_count ?? 0}/${prefetch?.total ?? 0}` : 'UMS connected'
    : waiting
      ? status?.verification_required ? 'Finish verification' : 'Sign in to UMS'
      : 'UMS not connected'
  const hint = connected
    ? loading
      ? `Reading ${ITEM_LABELS[prefetch?.current ?? ''] ?? 'your data'}…`
      : failed.length
        ? `Couldn't read ${failed.map(([kind]) => ITEM_LABELS[kind] ?? kind).join(', ')} yet`
        : 'Your data is ready'
    : waiting
      ? 'Use the window that opened'
      : 'Connect for your own data'

  return (
    <div className={`ums-card ${tone}`} title={status?.last_error || status?.message || ''}>
      <div className="ums-line">
        <span className="ums-dot" aria-hidden="true" />
        <strong>{label}</strong>
      </div>
      <p className="ums-hint">{hint}</p>
      {loading && prefetch && (
        <div className="ums-progress" aria-hidden="true">
          <span style={{ width: `${(100 * prefetch.ready_count) / Math.max(prefetch.total, 1)}%` }} />
        </div>
      )}
      <div className="ums-actions">
        {connected ? (
          <>
            <button onClick={onRefresh} disabled={busy}>Refresh</button>
            <button onClick={onDisconnect} disabled={busy}>Disconnect</button>
          </>
        ) : (
          <button className="primary" onClick={onConnect} disabled={busy}>
            {busy ? 'Opening…' : waiting ? 'Show UMS window' : 'Connect UMS'}
          </button>
        )}
      </div>
    </div>
  )
}
