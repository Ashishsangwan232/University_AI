import type { UMSSessionStatus } from '../../api/campusApi'

type Props = {
  status: UMSSessionStatus | null
  busy: boolean
  onConnect: () => void
  onRefresh: () => void
  onDisconnect: () => void
}

/** One line saying whether the bot can read the student's UMS data right now. */
export function UMSBar({ status, busy, onConnect, onRefresh, onDisconnect }: Props) {
  const connected = Boolean(status?.browser_connected && status?.authenticated)
  const waiting = Boolean(status?.running && !connected)

  const tone = connected ? 'ok' : waiting ? 'wait' : 'off'
  const label = connected
    ? 'UMS connected'
    : waiting
      ? status?.verification_required
        ? 'Finish the verification in the UMS window'
        : 'Sign in to UMS in the window that opened'
      : 'UMS not connected'
  const hint = connected
    ? 'Ask about your attendance, timetable, notices, messages or leave.'
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
    </div>
  )
}
