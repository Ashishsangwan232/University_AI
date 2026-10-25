import { Fragment, useEffect, useState } from 'react'
import { PageTitle } from '../components/ui/PageTitle'
import {
  draftLeave, getLeave, prefillLeave,
  type ApiError, type LeaveDraftInput, type LeaveDraftResult,
  type LeavePrefillResult, type LeaveResponse,
} from '../api/campusApi'

const UMS_LEAVE_URL = 'https://ums.lpu.in/lpuums/frmStudentHostelLeaveApplicationTermWise.aspx'

const cardStyle: React.CSSProperties = {
  border: '1px solid rgba(0,0,0,.10)', borderRadius: 14, padding: '18px 20px',
  display: 'flex', flexDirection: 'column', gap: 6, minWidth: 200, flex: '1 1 220px',
}

function BalanceCard({ title, balance }: { title: string; balance: Record<string, number> }) {
  const total = balance.total ?? 0
  const left = balance.balance ?? 0
  const used = balance.availed ?? Math.max(0, total - left)
  const pct = total > 0 ? Math.round((left / total) * 100) : 0
  return (
    <div style={cardStyle}>
      <span className="eyebrow">{title}</span>
      <strong style={{ fontSize: 32, lineHeight: 1.1 }}>{left}</strong>
      <span style={{ opacity: .7, fontSize: 13 }}>days remaining of {total}</span>
      <div className="progress" style={{ marginTop: 6 }}>
        <span style={{ width: `${Math.min(100, pct)}%` }} />
      </div>
      <small style={{ opacity: .65 }}>{used} availed</small>
    </div>
  )
}

/**
 * Hostel leave, read only.
 *
 * CampusAI reads the balances and shows them here. It does not fill the form,
 * tick the acknowledgement, or submit anything - applying stays the student's
 * own action, so this page links them to UMS rather than doing it for them.
 */
export default function Leave() {
  const [data, setData] = useState<LeaveResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const [draft, setDraft] = useState<LeaveDraftInput>({
    leave_type: '', start: '', end: '', visit_place: '', reason: '',
  })
  const [review, setReview] = useState<LeaveDraftResult | null>(null)
  const [checking, setChecking] = useState(false)
  const [prefill, setPrefill] = useState<LeavePrefillResult | null>(null)
  const [prefilling, setPrefilling] = useState(false)
  const [prefillError, setPrefillError] = useState('')

  const set = (key: keyof LeaveDraftInput) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>,
  ) => {
    setDraft(current => ({ ...current, [key]: e.target.value }))
    setReview(null)
    setPrefill(null)
  }

  const check = () => {
    setChecking(true)
    setPrefillError('')
    draftLeave(draft)
      .then(setReview)
      .catch(reason => setPrefillError((reason as ApiError).message || 'Could not check the draft.'))
      .finally(() => setChecking(false))
  }

  const fillInUms = () => {
    setPrefilling(true)
    setPrefillError('')
    prefillLeave(draft)
      .then(result => { setPrefill(result); load() })
      .catch(reason => setPrefillError((reason as ApiError).message || 'Could not fill the UMS form.'))
      .finally(() => setPrefilling(false))
  }

  const load = () => {
    setLoading(true)
    getLeave()
      .then(response => { setData(response); setError('') })
      .catch(reason => setError((reason as ApiError).message || 'Could not read your leave balance.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const balances = data?.balances ?? {}
  const profile = data?.profile ?? {}
  const named: Record<string, string> = { day: 'Day leave', night: 'Night leave', leave: 'Leave' }

  return (
    <div className="section-page">
      <PageTitle
        eyebrow="Read only"
        title="Hostel leave"
        desc="Your leave balance and who approves it, read from UMS. CampusAI does not submit leave applications."
      />

      {error && (
        <div className="panel empty-state">
          <h2>Leave balance needs a UMS session</h2>
          <p>{error}</p>
          <button className="secondary-btn" type="button" onClick={load}>Try again</button>
          <small>Open Profile and click Connect UMS, then sign in yourself in the CampusAI browser.</small>
        </div>
      )}

      {loading && !error && <div className="panel empty-state"><p>Reading your leave balance from UMS…</p></div>}

      {!error && !loading && data && (
        <>
          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginBottom: 18 }}>
            {Object.entries(balances).map(([kind, balance]) => (
              <BalanceCard key={kind} title={named[kind] ?? kind} balance={balance} />
            ))}
          </div>

          <div className="panel" style={{ padding: '18px 20px', marginBottom: 18 }}>
            <div className="panel-header"><div><h2>Your hostel</h2><p>{data.source}</p></div></div>
            <div className="profile-details">
              {profile.hostel && <div><span>Hostel</span><strong>{profile.hostel}</strong></div>}
              {profile.room && <div><span>Room</span><strong>{profile.room}</strong></div>}
              {profile.term && <div><span>Term</span><strong>{profile.term}</strong></div>}
              {profile.recommending_authority && (
                <div><span>Recommending</span><strong>{profile.recommending_authority}</strong></div>
              )}
              {profile.sanctioning_authority && (
                <div><span>Sanctioning</span><strong>{profile.sanctioning_authority}</strong></div>
              )}
            </div>
            {data.leave_types.length > 0 && (
              <p style={{ marginTop: 12, fontSize: 13, opacity: .8 }}>
                Leave types available this term: {data.leave_types.join(', ')}.
              </p>
            )}
          </div>

          <div className="panel" style={{ padding: '18px 20px', marginBottom: 18 }}>
            <div className="panel-header">
              <div>
                <h2>Draft an application</h2>
                <p>CampusAI checks the dates and your balance. It does not submit.</p>
              </div>
            </div>

            <div className="calculator-controls" style={{ flexWrap: 'wrap', gap: 12 }}>
              <label style={{ flex: '1 1 220px' }}>
                Leave type
                <select value={draft.leave_type} onChange={set('leave_type')}>
                  <option value="">Select…</option>
                  {(data.leave_types || []).map(type => <option key={type} value={type}>{type}</option>)}
                </select>
              </label>
              <label style={{ flex: '1 1 200px' }}>
                Start
                <input type="datetime-local" value={draft.start} onChange={set('start')} />
              </label>
              <label style={{ flex: '1 1 200px' }}>
                End
                <input type="datetime-local" value={draft.end} onChange={set('end')} />
              </label>
              <label style={{ flex: '1 1 200px' }}>
                Visiting
                <input value={draft.visit_place} onChange={set('visit_place')} placeholder="Where are you going?" />
              </label>
              <label style={{ flex: '1 1 100%' }}>
                Reason
                <textarea value={draft.reason} onChange={set('reason')} rows={2}
                          placeholder="Why are you leaving the hostel?" style={{ width: '100%' }} />
              </label>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
              <button className="secondary-btn" type="button" onClick={check} disabled={checking}>
                {checking ? 'Checking…' : 'Check this draft'}
              </button>
            </div>

            {review && (
              <div className={`calculator-result ${review.ok ? 'safe' : 'warning'}`} style={{ marginTop: 14, display: 'block' }}>
                <strong style={{ display: 'block', marginBottom: 6 }}>
                  {review.ok ? 'Draft looks valid' : 'This draft cannot be used yet'}
                </strong>
                <p style={{ margin: 0, fontSize: 13 }}>{review.summary}</p>
                {review.errors.map(message => (
                  <p key={message} className="form-error" style={{ margin: '6px 0 0', fontSize: 13 }}>{message}</p>
                ))}
                {review.warnings.map(message => (
                  <p key={message} style={{ margin: '6px 0 0', fontSize: 13, opacity: .8 }}>⚠ {message}</p>
                ))}

                {review.ok && (
                  <div style={{ display: 'flex', gap: 10, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                    <button className="secondary-btn" type="button" onClick={fillInUms} disabled={prefilling}>
                      {prefilling ? 'Typing into UMS…' : 'Fill in UMS'}
                    </button>
                    <button className="primary-btn" type="button" disabled
                            title="CampusAI never submits a leave application. Submit it yourself in the UMS window.">
                      Submit
                    </button>
                    <small style={{ opacity: .7 }}>Submit is deliberately disabled — you press it in UMS.</small>
                  </div>
                )}
              </div>
            )}

            {prefillError && <p className="form-error" style={{ marginTop: 10 }}>{prefillError}</p>}

            {prefill && (
              <div className="calculator-result safe" style={{ marginTop: 14, display: 'block' }}>
                <strong style={{ display: 'block', marginBottom: 6 }}>
                  Form filled — submitted: {String(prefill.submitted)}
                </strong>
                <p style={{ margin: 0, fontSize: 13 }}>{prefill.next_step}</p>
                <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '2px 12px',
                             margin: '10px 0 0', fontSize: 12 }}>
                  {Object.entries(prefill.form_now).map(([label, value]) => (
                    <Fragment key={label}>
                      <dt style={{ opacity: .65 }}>{label}</dt>
                      <dd style={{ margin: 0 }}>{value || <em style={{ opacity: .6 }}>empty</em>}</dd>
                    </Fragment>
                  ))}
                </dl>
                <p style={{ margin: '8px 0 0', fontSize: 12, opacity: .75 }}>
                  Acknowledgement ticked: {String(prefill.acknowledgement_ticked)} — CampusAI never ticks it.
                </p>
                {prefill.refused.length > 0 && (
                  <p className="form-error" style={{ margin: '8px 0 0', fontSize: 12 }}>
                    Not filled: {prefill.refused.map(r => `${r.label} (${r.reason})`).join(', ')}
                  </p>
                )}
              </div>
            )}
          </div>

          <div className="panel" style={{ padding: '18px 20px' }}>
            <div className="panel-header">
              <div>
                <h2>Submitting is yours</h2>
                <p>CampusAI stops at a filled form</p>
              </div>
            </div>
            <p style={{ fontSize: 14, opacity: .85, margin: '0 0 12px' }}>
              CampusAI reads your balance but does not submit leave applications. A leave request
              commits you to an acknowledgement about disciplinary action, so it should be your own
              deliberate act — not something an assistant does on your behalf.
            </p>
            <ol style={{ fontSize: 13, opacity: .8, paddingLeft: 20, margin: '0 0 14px' }}>
              <li>Open the CampusAI browser window where you signed in to UMS.</li>
              <li>Go to Hostel Leave Application.</li>
              <li>Pick the leave type and dates, give your reason, tick the acknowledgement.</li>
              <li>Submit it yourself, then come back here and refresh to see the updated balance.</li>
            </ol>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <a className="secondary-btn" href={UMS_LEAVE_URL} target="_blank" rel="noreferrer">
                Open the form in UMS
              </a>
              <button className="text-btn" type="button" onClick={load}>Refresh balance</button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
