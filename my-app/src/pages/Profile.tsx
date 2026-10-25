import { useState } from 'react'
import { describeUMSState, type StudentProfile, type UMSSessionStatus } from '../api/campusApi'
import { describeStudent, initials as initialsOf } from '../utils/student'

type Props = {
  student: StudentProfile
  studentError?: string
  portalConnected: boolean
  umsStatus: UMSSessionStatus | null
  onConnectUms: () => void
  onRefreshUms: () => void
}

export function Profile({ student, studentError, portalConnected, umsStatus, onConnectUms, onRefreshUms }: Props) {
  const [notifications, setNotifications] = useState(true)
  const [compact, setCompact] = useState(false)
  const [saved, setSaved] = useState(false)
  const save = () => { setSaved(true); window.setTimeout(() => setSaved(false), 1800) }
  const initials = initialsOf(student)
  const detail = describeStudent(student)

  const connected = portalConnected || umsStatus?.attendance_captured === true
  const message = umsStatus?.message || 'Credentials stay inside the dedicated browser and are never sent to CampusAI or to Gemini.'

  return <div className="profile-page">
    <section className="page-title profile-title"><div><div className="eyebrow">Account</div><h1>Profile & settings</h1><p>Manage your student details, portal connection, and CampusAI preferences.</p></div>{saved && <span className="saved-pill">✓ Changes saved</span>}</section>
    <section className="profile-grid">
      <div className="panel profile-card profile-main-card">
        <div className="profile-identity">
          <div className="profile-avatar-large">{initials}</div>
          <div>
            <h2>{student.name || 'Name not read from UMS'}</h2>
            {detail && <p>{detail}</p>}
          </div>
        </div>
        <div className="profile-details">
          {student.student_id && <div><span>Registration no</span><strong>{student.student_id}</strong></div>}
          {student.term && <div><span>Term</span><strong>{student.term}</strong></div>}
          {student.semester != null && <div><span>Semester</span><strong>{student.semester}</strong></div>}
          {student.program && <div><span>Program</span><strong>{student.program}</strong></div>}
          {student.department && <div><span>Department</span><strong>{student.department}</strong></div>}
          {student.section && <div><span>Section</span><strong>{student.section}</strong></div>}
          {student.hostel && <div><span>Hostel</span><strong>{student.hostel}</strong></div>}
          {student.room && <div><span>Room</span><strong>{student.room}</strong></div>}
        </div>
        {studentError && <p className="form-error" style={{ fontSize: 13 }}>{studentError}</p>}
        <div className="profile-note">
          <span>ⓘ</span>
          <p>
            {student.live
              ? `Read from your UMS session${student.name_source ? ` (name from the ${student.name_source} reading)` : ''}. CampusAI only reads these fields — it never changes them.`
              : 'These are demo details. Connect UMS and sign in yourself to see your real name and registration number.'}
          </p>
        </div>
      </div>

      <div className="panel settings-card"><div className="panel-header"><div><h2>Preferences</h2><p>Control how CampusAI behaves</p></div></div><SettingRow title="Announcements" description="Show new college notice notifications" checked={notifications} onChange={setNotifications} /><SettingRow title="Compact layout" description="Use tighter spacing on larger screens" checked={compact} onChange={setCompact} /></div>

      <div className="panel connection-card">
        <div className="panel-header">
          <div><h2>UMS session</h2><p>Playwright-controlled browser used for private student data</p></div>
          <span className={`connection-badge ${connected ? 'connected' : ''}`}>{connected ? 'Live' : 'Not connected'}</span>
        </div>
        <div className="connection-body">
          <div className="connection-icon">↔</div>
          <div>
            <strong>{describeUMSState(umsStatus)}</strong>
            <p>{message}</p>
            {umsStatus && <p style={{ fontSize: 12, opacity: .7 }}>
              State: <code>{umsStatus.state}</code>
              {umsStatus.attendance_course_count > 0 && ` · ${umsStatus.attendance_course_count} courses captured`}
              {umsStatus.diagnostics?.current_url && <> · {umsStatus.diagnostics.current_url}</>}
            </p>}
            {umsStatus?.last_error && <p className="form-error" style={{ fontSize: 12 }}>{umsStatus.last_error}</p>}
          </div>
        </div>
        <div className="connection-actions">
          <button className="secondary-btn" onClick={onConnectUms}>{umsStatus?.running ? 'Open UMS window' : 'Connect UMS'}</button>
          <button className="text-btn" onClick={onRefreshUms}>Refresh from UMS</button>
        </div>
        <ol style={{ fontSize: 12, opacity: .8, paddingLeft: 18, margin: '10px 0 0' }}>
          <li>Click Connect UMS — CampusAI opens its own dedicated browser window.</li>
          <li>Type your username and password yourself, in that window.</li>
          <li>Complete the human-verification check yourself. CampusAI never touches it.</li>
          <li>Once the dashboard loads, Playwright takes over and reads your attendance.</li>
        </ol>
      </div>

      <div className="panel privacy-card">
        <div className="panel-header"><div><h2>Privacy & safety</h2><p>How CampusAI handles sensitive actions</p></div></div>
        <ul>
          <li><span>✓</span><div><strong>Credentials never leave the browser</strong><small>CampusAI does not read, store, type, or log your UMS username, password, or OTP, and never sends them to Gemini.</small></div></li>
          <li><span>✓</span><div><strong>Human verification stays manual</strong><small>Verification checks are completed by you. Nothing is bypassed or automated.</small></div></li>
          <li><span>✓</span><div><strong>No silent fallback</strong><small>If UMS is connected but attendance cannot be read, CampusAI says so instead of showing demo numbers.</small></div></li>
          <li><span>✓</span><div><strong>AI does not calculate attendance</strong><small>Attendance arithmetic runs in backend code, not in the language model.</small></div></li>
        </ul>
        <button className="primary-btn" onClick={save}>Save preferences</button>
      </div>
    </section>
  </div>
}

function SettingRow({ title, description, checked, onChange }: { title: string; description: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <label className="setting-row"><span><strong>{title}</strong><small>{description}</small></span><input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} /><i aria-hidden="true" /></label>
}
