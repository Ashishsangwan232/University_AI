import type { Page } from '../../types'
import type { StudentProfile } from '../../api/campusApi'
import { navItems } from '../../data/mockData'
import { initials } from '../../utils/student'

type Props = { page: Page; onMenu: () => void; notificationsOpen: boolean; setNotificationsOpen: (open: boolean) => void; navigate: (page: Page) => void; student: StudentProfile | null }

export function Topbar({ page, onMenu, notificationsOpen, setNotificationsOpen, navigate, student }: Props) {
  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={onMenu} aria-label="Open navigation menu">☰</button>
      <div className="breadcrumb"><span>Student portal</span><i>/</i><strong>{navItems.find((n) => n.id === page)?.label}</strong></div>
      <div className="top-actions">
        <div className="notification-wrap">
          <button className="icon-button" onClick={() => setNotificationsOpen(!notificationsOpen)} aria-label="Notifications">♢<span className="notification-dot" /></button>
          {notificationsOpen && <div className="notification-popover"><strong>Notifications</strong><p>3 announcements need your attention.</p><button onClick={() => { navigate('announcements'); setNotificationsOpen(false) }}>View announcements →</button></div>}
        </div>
        <button className="top-avatar top-avatar-button" onClick={() => navigate('profile')} aria-label="Open profile settings" title={student?.name || 'Not signed in'}>{initials(student)}</button>
      </div>
    </header>
  )
}
