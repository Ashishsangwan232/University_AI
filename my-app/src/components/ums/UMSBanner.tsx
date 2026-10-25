import { useState } from 'react'
import { describeUMSState, type AttendanceResponse, type UMSSessionStatus } from '../../api/campusApi'

type Props = {
  status: UMSSessionStatus | null
  attendance: AttendanceResponse | null
  attendanceError: string
  connecting: boolean
  onConnect: () => void
  onRefresh: () => void
}

const shell: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
  padding: '10px 14px', borderRadius: 12, marginBottom: 16,
  border: '1px solid rgba(0,0,0,.08)', fontSize: 13, lineHeight: 1.45,
}

const dot = (color: string): React.CSSProperties => ({
  width: 8, height: 8, borderRadius: '50%', background: color, flex: '0 0 auto',
})

/**
 * Always tells the student whether the numbers on screen are live UMS data or
 * demo data, and exactly which state the UMS pipeline stopped in. This is the
 * UI half of the "no silent fallback" rule.
 */
export function UMSBanner({ status, attendance, attendanceError, connecting, onConnect, onRefresh }: Props) {
  const [showDetails, setShowDetails] = useState(false)
  const live = attendance?.live === true
  const diagnostics = status?.diagnostics

  const tone = live
    ? { bg: 'rgba(34,160,90,.08)', border: 'rgba(34,160,90,.35)', dotColor: '#22a05a' }
    : attendanceError
      ? { bg: 'rgba(200,60,50,.08)', border: 'rgba(200,60,50,.35)', dotColor: '#c83c32' }
      : { bg: 'rgba(210,150,30,.10)', border: 'rgba(210,150,30,.35)', dotColor: '#d2961e' }

  const headline = live
    ? `Live UMS attendance — ${attendance?.subjects.length ?? 0} courses from your portal`
    : attendanceError
      ? attendanceError
      : 'Showing demo data. Connect UMS to see your real attendance.'

  return (
    <div style={{ ...shell, background: tone.bg, borderColor: tone.border }}>
      <span style={dot(tone.dotColor)} aria-hidden="true" />
      <div style={{ flex: '1 1 260px', minWidth: 220 }}>
        <strong style={{ display: 'block' }}>{headline}</strong>
        <span style={{ opacity: .75 }}>
          {describeUMSState(status)}
          {status?.state ? ` · ${status.state}` : ''}
          {attendance?.source ? ` · ${attendance.source}` : ''}
        </span>
      </div>
      {!live && (
        <button className="secondary-btn" onClick={onConnect} disabled={connecting}>
          {connecting ? 'Opening…' : status?.running ? 'Open UMS window' : 'Connect UMS'}
        </button>
      )}
      <button className="text-btn" onClick={onRefresh}>Refresh from UMS</button>
      {diagnostics && (
        <button className="text-btn" onClick={() => setShowDetails(value => !value)}>
          {showDetails ? 'Hide details' : 'Details'}
        </button>
      )}

      {showDetails && diagnostics && (
        <dl style={{ flexBasis: '100%', display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '2px 14px', margin: '8px 0 0', fontSize: 12, opacity: .85 }}>
          <Row label="State" value={diagnostics.state} />
          <Row label="UMS tabs found" value={`${diagnostics.ums_page_count} of ${diagnostics.page_count} open tabs`} />
          <Row label="Current page" value={diagnostics.current_url ?? '—'} />
          <Row label="Authenticated" value={String(diagnostics.authenticated)} />
          <Row label="Verification showing" value={String(diagnostics.verification_required)} />
          <Row label="Navigation attempts" value={diagnostics.navigation_attempts.join(' · ') || '—'} />
          <Row label="Attendance page" value={diagnostics.attendance_url ?? 'not reached'} />
          <Row label="Frames searched" value={String(diagnostics.frame_count)} />
          <Row label="Tables scanned" value={String(diagnostics.tables_scanned)} />
          <Row label="Table headers" value={diagnostics.table_headers.join(' | ') || '—'} />
          <Row label="Courses parsed" value={String(diagnostics.courses_parsed)} />
          <Row label="Validated" value={diagnostics.validation_error ?? String(diagnostics.validated)} />
          <Row label="Last error" value={diagnostics.last_error ?? '—'} />
        </dl>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return <>
    <dt style={{ opacity: .65 }}>{label}</dt>
    <dd style={{ margin: 0, wordBreak: 'break-word' }}>{value}</dd>
  </>
}
