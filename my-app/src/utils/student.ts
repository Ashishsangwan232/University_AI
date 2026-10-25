import type { StudentProfile } from '../api/campusApi'

/**
 * The greeting, from the clock rather than from an assumption.
 *
 * The dashboard used to say "Good morning" at every hour of the day.
 */
export function greeting(now: Date = new Date()): string {
  const hour = now.getHours()
  if (hour >= 5 && hour < 12) return 'Good morning'
  if (hour >= 12 && hour < 17) return 'Good afternoon'
  return 'Good evening'
}

/** What to call the student. Empty when UMS has not told us yet. */
export function firstName(student: StudentProfile | null): string {
  const name = (student?.name || '').trim()
  return name ? name.split(/\s+/)[0] : ''
}

/** Avatar initials, at most two letters. */
export function initials(student: StudentProfile | null): string {
  const parts = (student?.name || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '—'
  return parts.slice(0, 2).map(part => part[0]).join('').toUpperCase()
}

const ORDINALS = ['', 'st', 'nd', 'rd']
const ordinal = (n: number) => `${n}${ORDINALS[n] ?? 'th'}`

/**
 * The line under the student's name.
 *
 * Only from fields UMS actually returned - no placeholder programme, no
 * invented year. When nothing is known this is empty and the caller shows
 * nothing rather than a fabricated course.
 */
export function describeStudent(student: StudentProfile | null): string {
  if (!student) return ''
  const bits = [student.program, student.department]
    .map(value => (value || '').trim())
    .filter(Boolean)
  if (student.year) bits.push(`${ordinal(student.year)} Year`)
  else if (student.term) bits.push(String(student.term).trim())
  if (!bits.length && student.student_id) bits.push(student.student_id)
  return bits.join(' · ')
}
