import type { Announcement, ClassItem, Subject } from '../types'

export const navItems = [
  { id: 'dashboard' as const, label: 'Dashboard', icon: '⌂' },
  { id: 'chat' as const, label: 'Ask AI', icon: '✦' },
  { id: 'attendance' as const, label: 'Attendance', icon: '◷' },
  { id: 'timetable' as const, label: 'Timetable', icon: '▦' },
  { id: 'announcements' as const, label: 'Announcements', icon: '◉' },
  { id: 'messages' as const, label: 'Messages', icon: '✉' },
  { id: 'leave' as const, label: 'Hostel Leave', icon: '↗' },
  { id: 'services' as const, label: 'College Services', icon: '◇' },
  { id: 'profile' as const, label: 'Profile & Settings', icon: '◎' },
]

export const subjects: Subject[] = [
  { name: 'Database Management', short: 'DBMS', attended: 32, total: 40, teacher: 'Dr. Mehta' },
  { name: 'Operating Systems', short: 'OS', attended: 35, total: 45, teacher: 'Prof. Sharma' },
  { name: 'Computer Networks', short: 'CN', attended: 28, total: 32, teacher: 'Dr. Kapoor' },
  { name: 'Mathematics III', short: 'MATH', attended: 30, total: 40, teacher: 'Dr. Verma' },
]

export const announcements: Announcement[] = [
  { title: 'Mid-semester examination registration', date: 'Sep 15', tag: 'Important', text: 'Complete your examination registration before September 15.' },
  { title: 'Department seminar — AI in Healthcare', date: 'Sep 12', tag: 'CSE', text: 'A department seminar is scheduled for Friday at 11:00 AM in Seminar Hall 2.' },
  { title: 'Hostel maintenance notice', date: 'Sep 10', tag: 'Hostel', text: 'Routine maintenance will take place in Blocks B and C from 10 AM to 2 PM.' },
]

export const classes: ClassItem[] = [
  { time: '09:00', end: '10:00', subject: 'Computer Networks', room: 'Room 204', teacher: 'Dr. Kapoor', active: true },
  { time: '10:15', end: '11:15', subject: 'Database Management', room: 'Lab 3', teacher: 'Dr. Mehta', active: false },
  { time: '11:30', end: '12:30', subject: 'Mathematics III', room: 'Room 118', teacher: 'Dr. Verma', active: false },
  { time: '14:00', end: '15:00', subject: 'Operating Systems', room: 'Room 205', teacher: 'Prof. Sharma', active: false },
]
