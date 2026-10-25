import type { Page } from '../../types'
import type { StudentProfile } from '../../api/campusApi'
import { navItems } from '../../data/mockData'
import { describeStudent, initials } from '../../utils/student'

type Props = {
  page: Page
  open: boolean
  navigate: (page: Page) => void
  student: StudentProfile | null
  portalConnected: boolean
}

/**
 * The sidebar used to hard-code a demo student's name, initials and course.
 * Everything identifying the student now comes from UMS, and the portal status
 * reflects the real session instead of always claiming to be connected.
 */
export function Sidebar({ page, open, navigate, student, portalConnected }: Props) {
  const name = (student?.name || '').trim()
  const detail = describeStudent(student)

  return (
    <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Student navigation">
      <div className="brand">
        <div className="brand-mark">✦</div>
        <div><strong>CampusAI</strong><span>Student assistant</span></div>
      </div>
      <div className="sidebar-label">Workspace</div>
      <nav>
        {navItems.map((item) => (
          <button key={item.id} className={`nav-item ${page === item.id ? 'active' : ''}`} onClick={() => navigate(item.id)}>
            <span className="nav-icon" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="portal-status">
          <span className="status-dot" style={portalConnected ? undefined : { background: '#c9c9c9' }} />
          <div>
            <strong>{portalConnected ? 'Portal connected' : 'Portal not connected'}</strong>
            <small>{portalConnected ? 'Student session active' : 'Sign in to UMS to see your data'}</small>
          </div>
        </div>
        <button className="profile-mini" onClick={() => navigate('profile')}>
          <span className="avatar">{initials(student)}</span>
          <span>
            <strong>{name || 'Not signed in'}</strong>
            <small>{detail || (student?.live ? 'Read from UMS' : 'Connect UMS to load your details')}</small>
          </span>
          <span className="more">•••</span>
        </button>
      </div>
    </aside>
  )
}
