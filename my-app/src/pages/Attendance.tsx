import { useEffect, useMemo, useState } from 'react'
import {
  calculateAttendance, getAttendanceDetail,
  type ApiError, type AttendanceCalculateResponse, type AttendanceSubject, type CourseDetail,
} from '../api/campusApi'
import { PageTitle } from '../components/ui/PageTitle'

type Props = { overall: number; subjects: AttendanceSubject[]; live: boolean; source: string }

type SubjectRow = AttendanceSubject

function getPercent(attended: number, total: number) {
  return total === 0 ? 0 : (attended / total) * 100
}

function ClassLog({ detail }: { detail: CourseDetail }) {
  const missed = detail.entries.filter(entry => entry.status === 'absent')
  return (
    <div style={{ gridColumn: '1 / -1', margin: '4px 0 2px', fontSize: 13 }}>
      <div style={{ opacity: .75, marginBottom: 6 }}>
        {detail.recorded} classes recorded · {detail.present} present · {detail.absent} absent
      </div>
      {missed.length === 0 ? (
        <div style={{ opacity: .7 }}>No absences recorded for this course.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 420 }}>
            <thead>
              <tr style={{ textAlign: 'left', opacity: .6 }}>
                <th style={{ padding: '4px 8px 4px 0' }}>Date</th>
                <th style={{ padding: '4px 8px' }}>Time</th>
                <th style={{ padding: '4px 8px' }}>Type</th>
                <th style={{ padding: '4px 8px' }}>Reason</th>
              </tr>
            </thead>
            <tbody>
              {missed.map((entry, index) => (
                <tr key={`${entry.date}-${entry.time}-${index}`}>
                  <td style={{ padding: '4px 8px 4px 0' }}>{entry.date}</td>
                  <td style={{ padding: '4px 8px' }}>{entry.time || '—'}</td>
                  <td style={{ padding: '4px 8px' }}>{entry.type || '—'}</td>
                  <td style={{ padding: '4px 8px', opacity: .75 }}>{entry.reason || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function AttendanceSubject({ subject, detail }: { subject: SubjectRow; detail?: CourseDetail }) {
  const pct = getPercent(subject.attended, subject.total)
  const rounded = Math.round(pct)
  const [result, setResult] = useState<AttendanceCalculateResponse | null>(null)
  const [showLog, setShowLog] = useState(false)

  useEffect(() => {
    let active = true
    calculateAttendance(subject.attended, subject.total, 75)
      .then(data => { if (active) setResult(data) })
      .catch(() => { if (active) setResult(null) })
    return () => { active = false }
  }, [subject.attended, subject.total])

  const status = pct >= 80 ? 'Strong' : pct >= 75 ? 'On track' : 'Needs attention'
  const margin = result
    ? pct >= 75
      ? `${result.can_miss} class${result.can_miss === 1 ? '' : 'es'} can be missed before 75%.`
      : `Attend ${result.must_attend} more class${result.must_attend === 1 ? '' : 'es'} to reach 75%.`
    : 'Checking attendance margin…'

  return (
    <div className="attendance-table-row">
      <div className="table-subject">
        <span className="subject-code">{subject.short}</span>
        <span><strong>{subject.name}</strong><small>{subject.teacher}</small></span>
      </div>
      <div className="table-bar">
        <div className="progress"><span style={{ width: `${Math.min(100, pct)}%` }} /></div>
        <small>{subject.attended} / {subject.total}</small>
      </div>
      <strong className={pct < 75 ? 'danger-text' : ''}>{rounded}%</strong>
      <span className={`status-pill ${pct < 75 ? 'danger-pill' : ''}`}>{status}</span>
      <div className="attendance-row-detail">
        {margin}
        {detail && (
          <button className="text-btn" type="button" style={{ marginLeft: 10 }} onClick={() => setShowLog(open => !open)}>
            {showLog ? 'Hide classes' : `${detail.absent} missed · show classes`}
          </button>
        )}
      </div>
      {showLog && detail && <ClassLog detail={detail} />}
    </div>
  )
}

export function Attendance({ overall, subjects, live, source }: Props) {
  const [target, setTarget] = useState(75)
  const [selectedSubject, setSelectedSubject] = useState('overall')
  const [calculator, setCalculator] = useState<AttendanceCalculateResponse | null>(null)
  const [calculating, setCalculating] = useState(false)
  const [calculatorError, setCalculatorError] = useState('')
  const [detail, setDetail] = useState<Record<string, CourseDetail>>({})
  const [detailError, setDetailError] = useState('')

  // The class-by-class log lives in the same UMS modal as the summary, so it is
  // only available on a live session. Its absence is never fatal.
  useEffect(() => {
    let active = true
    if (!live) { setDetail({}); return }
    getAttendanceDetail()
      .then(data => { if (active) { setDetail(data.courses ?? {}); setDetailError('') } })
      .catch(reason => { if (active) setDetailError((reason as ApiError).message || '') })
    return () => { active = false }
  }, [live])

  const overallRecords = useMemo(() => ({
    attended: subjects.reduce((sum, s) => sum + s.attended, 0),
    total: subjects.reduce((sum, s) => sum + s.total, 0),
  }), [subjects])

  const selectedRecords = useMemo(() => (
    selectedSubject === 'overall'
      ? overallRecords
      : subjects.find(s => s.short === selectedSubject) ?? overallRecords
  ), [selectedSubject, subjects, overallRecords])

  useEffect(() => {
    let active = true
    setCalculating(true)
    setCalculatorError('')

    calculateAttendance(selectedRecords.attended, selectedRecords.total, target)
      .then(data => {
        if (!active) return
        setCalculator(data)
        setCalculating(false)
      })
      .catch(error => {
        if (!active) return
        setCalculator(null)
        setCalculating(false)
        setCalculatorError(error instanceof Error ? error.message : 'Unable to calculate attendance.')
      })

    return () => { active = false }
  }, [selectedRecords, target])

  const targetReached = calculator ? calculator.current_percentage >= target : false

  return (
    <div className="section-page">
      <PageTitle
        eyebrow={live ? 'Live UMS data' : 'Demo data'}
        title="Attendance"
        desc="See your subject-wise attendance and calculate exactly how much room you have before a target percentage."
      />

      <div className="attendance-summary">
        <div className="summary-card big">
          <span>Overall attendance</span>
          <strong>{overall}%</strong>
          <div className="large-progress"><span style={{ width: `${Math.min(100, overall)}%` }} /></div>
          <small>{overallRecords.attended} / {overallRecords.total} classes · minimum required 75%</small>
        </div>
        <div className="summary-card">
          <span>Classes you can miss</span>
          <strong>{calculator && selectedSubject === 'overall' && target === 75 ? calculator.can_miss : '—'}</strong>
          <small>While keeping overall attendance at or above 75%.</small>
        </div>
        <div className="summary-card">
          <span>Classes attended</span>
          <strong>{overallRecords.attended}</strong>
          <small>Out of {overallRecords.total} recorded classes.</small>
        </div>
      </div>

      <div className="attendance-calculator panel">
        <div className="calculator-copy">
          <span className="eyebrow">Attendance planner</span>
          <h2>How many classes can I miss?</h2>
          <p>Choose a subject and your target attendance. The calculation runs in the CampusAI backend, not in the language model. Source: {source || 'unknown'}.</p>
        </div>
        <div className="calculator-controls">
          <label>
            Subject
            <select value={selectedSubject} onChange={e => setSelectedSubject(e.target.value)}>
              <option value="overall">Overall attendance</option>
              {subjects.map(subject => <option key={subject.short} value={subject.short}>{subject.short} — {subject.name}</option>)}
            </select>
          </label>
          <label>
            Target
            <div className="target-input">
              <input type="number" min="1" max="100" value={target} onChange={e => setTarget(Math.min(100, Math.max(1, Number(e.target.value) || 1)))} />
              <span>%</span>
            </div>
          </label>
        </div>
        <div className={`calculator-result ${targetReached ? 'safe' : 'warning'}`}>
          <div>
            <small>Current</small>
            <strong>{calculator ? `${calculator.current_percentage.toFixed(1)}%` : '—'}</strong>
          </div>
          <div className="result-arrow">→</div>
          <div>
            <small>Target</small>
            <strong>{target}%</strong>
          </div>
          <div className="result-answer">
            <small>{calculating ? 'Calculating' : calculatorError ? 'Error' : targetReached ? 'You can miss' : 'You need to attend'}</small>
            <strong>{calculatorError ? 'Try again' : calculator ? `${targetReached ? calculator.can_miss : calculator.must_attend} class${(targetReached ? calculator.can_miss : calculator.must_attend) === 1 ? '' : 'es'}` : '—'}</strong>
          </div>
        </div>
        {calculatorError && <p className="form-error">{calculatorError}</p>}
      </div>

      <div className="panel table-panel">
        <div className="panel-header">
          <div>
            <h2>Subject-wise attendance</h2>
            <p>
              {live ? 'Live from your UMS portal' : 'Demo records from PostgreSQL'}
              {live && Object.keys(detail).length > 0 && ' · class-by-class log available'}
              {live && detailError && ' · class log unavailable'}
            </p>
          </div>
          <span className="legend"><i /> 75% minimum</span>
        </div>
        <div className="attendance-table">
          {subjects.map(subject => (
            <AttendanceSubject key={subject.short} subject={subject} detail={detail[subject.short]} />
          ))}
        </div>
      </div>
    </div>
  )
}
