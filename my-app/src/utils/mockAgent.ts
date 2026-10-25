export function getMockReply(input: string) {
  const lower = input.toLowerCase()
  if (lower.includes('attendance') || lower.includes('miss') || lower.includes('skip')) return 'Your current overall attendance is 79.6%. The minimum is 75%. Based on the current records, you can miss up to 2 more classes while staying at or above the minimum. I’ll use your subject-wise records for a precise answer when the student portal is connected.'
  if (lower.includes('announcement') || lower.includes('notice')) return 'The most important current notice is about mid-semester examination registration. The deadline shown in the college notice is September 15. I can also explain the full notice or help you find the registration page.'
  if (lower.includes('leave')) return 'I can help prepare a hostel leave application. I’ll first identify the fields your hostel portal requires, ask you for anything missing, and show you the completed application before submission.'
  if (lower.includes('class') || lower.includes('timetable')) return 'Your next scheduled class is Computer Networks at 09:00 AM in Room 204 with Dr. Kapoor. You have four classes scheduled today.'
  return 'I can help with attendance, timetable, announcements, hostel leave, and finding college services. Try one of the suggested questions below.'
}
