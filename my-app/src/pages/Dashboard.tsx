import { useEffect, useState } from 'react'
import type { Page } from '../types'
import { calculateAttendance, type AttendanceSubject, type StudentProfile } from '../api/campusApi'
import { announcements, classes } from '../data/mockData'
import { describeStudent, firstName, greeting } from '../utils/student'
import { AnnouncementItem } from '../components/dashboard/AnnouncementItem'
import { QuickAction } from '../components/ui/QuickAction'
import { StatCard } from '../components/ui/StatCard'

type Props = { overall: number; subjects: AttendanceSubject[]; student: StudentProfile; navigate: (page: Page) => void }

export function Dashboard({ overall, subjects, student, navigate }: Props) {
  const nextClass = classes.find(item => item.active) ?? classes[0]
  const attended = subjects.reduce((sum, subject) => sum + subject.attended, 0)
  const total = subjects.reduce((sum, subject) => sum + subject.total, 0)
  const lowest = subjects.length
    ? [...subjects].sort((a, b) => (a.attended / a.total) - (b.attended / b.total))[0]
    : null

  // The margin is computed by the backend, never in the browser and never by
  // the language model.
  const [canMiss, setCanMiss] = useState<number | null>(null)
  useEffect(() => {
    let active = true
    if (!total) { setCanMiss(null); return }
    calculateAttendance(attended, total, 75)
      .then(data => { if (active) setCanMiss(data.can_miss) })
      .catch(() => { if (active) setCanMiss(null) })
    return () => { active = false }
  }, [attended, total])

  const canMissLabel = canMiss === null ? '—' : String(canMiss)

  // The greeting follows the clock instead of always saying "Good morning",
  // and the name comes from UMS - when UMS has not supplied one we greet the
  // student without a name rather than using a placeholder.
  const hello = greeting()
  const who = firstName(student)
  const subtitle = [
    student.semester ? `Semester ${student.semester}` : student.term,
    describeStudent(student).replace(/\s*·\s*\d+(?:st|nd|rd|th) Year$/, ''),
  ].filter(Boolean).join(' · ')

  return <>
    <section className="hero-row dashboard-hero">
      <div>
        {subtitle && <div className="eyebrow">{subtitle}</div>}
        <h1>{hello}{who && `, ${who}`} <span>👋</span></h1>
        <p>Your campus at a glance. Here’s what needs your attention today.</p>
      </div>
      <button className="primary-btn" onClick={() => navigate('chat')}>✦ Ask CampusAI</button>
    </section>

    <section className="stats-grid dashboard-stats">
      <StatCard label="Overall attendance" value={`${overall}%`} note="Required 75%" trend={overall >= 75 ? 'On track' : 'Needs attention'} icon="◷" onClick={() => navigate('attendance')} />
      <StatCard label="Classes you can miss" value={canMissLabel} note="While staying at 75%" trend="Safe margin" icon="✓" onClick={() => navigate('attendance')} />
      <StatCard label="Today's classes" value={`${classes.length}`} note={`Next at ${nextClass.time}`} trend="View timetable" icon="▦" onClick={() => navigate('timetable')} />
      <StatCard label="New announcements" value={`${announcements.length}`} note="1 marked important" trend="Read now" icon="◉" onClick={() => navigate('announcements')} />
    </section>

    <section className="dashboard-focus-grid">
      <div className="panel next-class-card">
        <div className="panel-header">
          <div><h2>Next class</h2><p>Today’s upcoming schedule</p></div>
          <button className="text-btn" onClick={() => navigate('timetable')}>Full timetable →</button>
        </div>
        <div className="next-class-body">
          <div className="next-class-time"><strong>{nextClass.time}</strong><span>{nextClass.end}</span></div>
          <div className="next-class-line" />
          <div className="next-class-info">
            <span className="live-pill">● Now</span>
            <h3>{nextClass.subject}</h3>
            <p>{nextClass.teacher} · {nextClass.room}</p>
          </div>
          <button className="secondary-btn" onClick={() => navigate('timetable')}>View class details</button>
        </div>
      </div>

      <div className="panel ai-insight-card">
        <div className="ai-insight-icon">✦</div>
        <div>
          <span className="eyebrow">CampusAI insight</span>
          <h2>{overall >= 75 ? 'Your attendance is on track' : 'Your attendance needs attention'}</h2>
          <p>
            You’re at <b>{overall}%</b> overall ({attended}/{total} classes).
            {lowest && <> <b>{lowest.short}</b> is your lowest-attendance subject, so it deserves the most attention this week.</>}
          </p>
          <button className="text-btn" onClick={() => navigate('chat')}>Ask AI about attendance →</button>
        </div>
      </div>
    </section>

    <section className="content-grid">
      <div className="panel attendance-panel">
        <div className="panel-header">
          <div><h2>Attendance overview</h2><p>Across your current semester</p></div>
          <button className="text-btn" onClick={() => navigate('attendance')}>View details →</button>
        </div>
        <div className="attendance-main">
          <div className="ring" style={{ background: `conic-gradient(var(--accent) 0 ${overall}%, #e7ece9 ${overall}% 100%)` }}>
            <div><strong>{overall}%</strong><span>overall</span></div>
          </div>
          <div className="attendance-copy">
            <strong>{overall >= 75 ? 'You’re above the minimum' : 'You’re below the minimum'}</strong>
            <p>You can miss up to <b>{canMissLabel} more classes</b> and stay at or above 75%, based on your current records.</p>
            <button className="secondary-btn" onClick={() => navigate('attendance')}>Check subject-wise attendance</button>
          </div>
        </div>
        <div className="subject-list">
          {subjects.map(s => <div className="subject-row" key={s.short}>
            <span className="subject-code">{s.short}</span>
            <span className="subject-name">{s.name}</span>
            <div className="progress"><span style={{ width: `${s.total ? (s.attended / s.total) * 100 : 0}%` }} /></div>
            <b>{s.total ? Math.round((s.attended / s.total) * 100) : 0}%</b>
          </div>)}
        </div>
      </div>

      <div className="panel quick-panel">
        <div className="panel-header"><div><h2>Quick actions</h2><p>Common student services</p></div></div>
        <div className="quick-actions">
          <QuickAction icon="↗" title="Apply hostel leave" desc="Create and submit a leave request" onClick={() => navigate('leave')} />
          <QuickAction icon="▦" title="Today's timetable" desc="See your classes and rooms" onClick={() => navigate('timetable')} />
          <QuickAction icon="◉" title="Read announcements" desc="Check notices from your college" onClick={() => navigate('announcements')} />
          <QuickAction icon="◇" title="Find a service" desc="Navigate to college services" onClick={() => navigate('services')} />
        </div>
      </div>
    </section>

    <section className="panel announcement-panel">
      <div className="panel-header"><div><h2>Important announcements</h2><p>Relevant updates from your college</p></div><button className="text-btn" onClick={() => navigate('announcements')}>See all →</button></div>
      <div className="announcement-list">{announcements.map((a, i) => <AnnouncementItem key={a.title} item={a} first={i === 0} />)}</div>
    </section>
  </>
}
