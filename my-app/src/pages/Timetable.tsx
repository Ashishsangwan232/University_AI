import { useEffect, useMemo, useState } from 'react'
import { PageTitle } from '../components/ui/PageTitle'
import { getTimetable, type ApiError, type TimetableClass, type TimetableResponse } from '../api/campusApi'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const SHORT: Record<string, string> = {
  Monday: 'Mon', Tuesday: 'Tue', Wednesday: 'Wed', Thursday: 'Thu',
  Friday: 'Fri', Saturday: 'Sat', Sunday: 'Sun',
}

const slotStyle: React.CSSProperties = {
  display: 'flex', gap: 14, alignItems: 'center', padding: '12px 16px',
  border: '1px solid rgba(0,0,0,.10)', borderRadius: 12,
}

function minutes(time: string) {
  const [hour, minute] = time.split(':').map(Number)
  return (hour || 0) * 60 + (minute || 0)
}

/** Live UMS timetable, grouped by day. Falls back to labelled demo rows only
 *  when no UMS session is connected. */
export default function Timetable() {
  const [data, setData] = useState<TimetableResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const todayName = DAYS[(new Date().getDay() + 6) % 7]
  const [day, setDay] = useState(todayName)

  const load = () => {
    setLoading(true)
    getTimetable()
      .then(response => { setData(response); setError('') })
      .catch(reason => setError((reason as ApiError).message || 'Could not load the timetable.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const classes = data?.classes ?? []
  const byDay = useMemo(() => {
    const grouped: Record<string, TimetableClass[]> = {}
    for (const item of classes) grouped[item.day || 'Unscheduled'] ??= []
    for (const item of classes) grouped[item.day || 'Unscheduled'].push(item)
    for (const list of Object.values(grouped)) list.sort((a, b) => minutes(a.time) - minutes(b.time))
    return grouped
  }, [classes])

  const daysWithClasses = DAYS.filter(d => (byDay[d]?.length ?? 0) > 0)
  const shown = byDay[day] ?? []
  const nowMinutes = new Date().getHours() * 60 + new Date().getMinutes()
  const isToday = day === todayName

  return (
    <div className="section-page">
      <PageTitle
        eyebrow={data?.live ? 'Live from UMS' : 'Demo data'}
        title="Timetable"
        desc="Your classes with rooms, class type and course codes, straight from UMS."
      />

      {error && (
        <div className="panel empty-state">
          <h2>Timetable unavailable</h2>
          <p>{error}</p>
          <button className="secondary-btn" type="button" onClick={load}>Try again</button>
        </div>
      )}

      {!error && (
        <>
          <div className="timetable-toolbar">
            <div>
              <span className="eyebrow">{data?.source ?? 'Loading'}</span>
              <h2>{day} · {shown.length} class{shown.length === 1 ? '' : 'es'}</h2>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="secondary-btn" type="button" onClick={() => setDay(todayName)}>Today</button>
              <button className="text-btn" type="button" onClick={load}>Refresh</button>
            </div>
          </div>

          <div className="filter-buttons" style={{ marginBottom: 14, flexWrap: 'wrap' }}>
            {DAYS.map(name => {
              const count = byDay[name]?.length ?? 0
              return (
                <button
                  key={name}
                  type="button"
                  className={`filter ${day === name ? 'active' : ''}`}
                  onClick={() => setDay(name)}
                  disabled={count === 0}
                  title={count === 0 ? 'No classes' : `${count} class(es)`}
                  style={count === 0 ? { opacity: .45 } : undefined}
                >
                  {SHORT[name]}{count > 0 ? ` · ${count}` : ''}
                </button>
              )
            })}
          </div>

          {loading && <div className="panel empty-state"><p>Reading your timetable from UMS…</p></div>}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {shown.map((item, index) => {
              const done = isToday && minutes(item.end) < nowMinutes
              const now = isToday && minutes(item.time) <= nowMinutes && nowMinutes < minutes(item.end)
              return (
                <div
                  key={`${item.day}-${item.time}-${item.subject}-${index}`}
                  style={{ ...slotStyle, opacity: done ? .55 : 1, borderColor: now ? 'rgba(34,160,90,.5)' : 'rgba(0,0,0,.10)' }}
                >
                  <div style={{ minWidth: 108 }}>
                    <strong>{item.time}</strong>
                    <div style={{ opacity: .6, fontSize: 12 }}>{item.end}</div>
                  </div>
                  <div style={{ flex: '1 1 auto' }}>
                    <strong>{item.subject}</strong>
                    <div style={{ opacity: .7, fontSize: 13 }}>
                      {item.room && <>{item.room}</>}
                      {item.type && <> · {item.type}</>}
                      {item.group && <> · {item.group}</>}
                    </div>
                  </div>
                  {now && <span className="status-pill">Now</span>}
                </div>
              )
            })}
          </div>

          {!loading && shown.length === 0 && (
            <div className="panel empty-state">
              <h2>No classes on {day}</h2>
              <p>
                {classes.length === 0
                  ? 'UMS returned no timetable entries.'
                  : `Classes are scheduled on ${daysWithClasses.join(', ') || 'no days'}.`}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
