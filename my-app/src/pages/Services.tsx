import { useMemo, useState } from 'react'
import type { Page } from '../types'
import { PageTitle } from '../components/ui/PageTitle'
import { ServiceCard, type Service } from '../components/services/ServiceCard'

type Props = { navigate: (page: Page) => void }

const services: Service[] = [
  { title: 'Bonafide certificate', category: 'Certificates', icon: '◇', description: 'Request a bonafide certificate for academic or official use.', action: 'View service', connected: false },
  { title: 'Examination registration', category: 'Examinations', icon: '▦', description: 'Open examination registration and related academic forms.', action: 'Open portal', connected: false },
  { title: 'Fee payment', category: 'Finance', icon: '₹', description: 'Find fee payment options and check the current payment flow.', action: 'Open portal', connected: false },
  { title: 'Hostel services', category: 'Accommodation', icon: '↗', description: 'Apply for hostel leave and access accommodation-related services.', action: 'Open service', connected: true },
  { title: 'Academic calendar', category: 'Academics', icon: '◷', description: 'Find semester dates, examinations, holidays and academic events.', action: 'View service', connected: false },
  { title: 'Student support', category: 'Support', icon: '?', description: 'Find common student support and help-desk services.', action: 'View service', connected: false },
]

const categories = ['All', ...Array.from(new Set(services.map(service => service.category)))]

export function Services({ navigate }: Props) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All')
  const [selected, setSelected] = useState<Service | null>(null)

  const filtered = useMemo(() => services.filter(service => {
    const matchesCategory = category === 'All' || service.category === category
    const text = `${service.title} ${service.category} ${service.description}`.toLowerCase()
    return matchesCategory && text.includes(query.toLowerCase().trim())
  }), [category, query])

  const openService = (service: Service) => {
    if (service.title === 'Hostel services') {
      navigate('leave')
      return
    }
    setSelected(service)
  }

  return (
    <div className="section-page">
      <PageTitle
        eyebrow="Find your way"
        title="College services"
        desc="Search common student services. CampusAI can also guide you here from chat."
      />

      <div className="services-toolbar">
        <div className="service-search">
          <span>⌕</span>
          <input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Search services..."
            aria-label="Search college services"
          />
          {query && <button onClick={() => setQuery('')} aria-label="Clear search">×</button>}
        </div>
        <div className="service-filters">
          {categories.map(item => (
            <button key={item} className={`filter ${category === item ? 'active' : ''}`} onClick={() => setCategory(item)}>
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="services-meta">
        <span>{filtered.length} service{filtered.length === 1 ? '' : 's'} available</span>
        <span>AI can help you find the right one</span>
      </div>

      {filtered.length > 0 ? (
        <div className="services-grid services-grid-new">
          {filtered.map(service => <ServiceCard key={service.title} service={service} onOpen={openService} />)}
        </div>
      ) : (
        <div className="service-empty">
          <span>⌕</span>
          <h2>No service found</h2>
          <p>Try a different search term or choose another category.</p>
          <button className="secondary-btn" onClick={() => { setQuery(''); setCategory('All') }}>Clear filters</button>
        </div>
      )}

      {selected && (
        <div className="service-modal-backdrop" onClick={() => setSelected(null)}>
          <div className="service-modal" role="dialog" aria-modal="true" onClick={event => event.stopPropagation()}>
            <button className="modal-close" onClick={() => setSelected(null)} aria-label="Close">×</button>
            <div className="service-modal-icon">{selected.icon}</div>
            <div className="eyebrow">{selected.category}</div>
            <h2>{selected.title}</h2>
            <p>{selected.description}</p>
            <div className="service-modal-note">
              <strong>Prototype status</strong>
              <span>This service is ready to connect to the college portal. The backend will handle the authenticated portal flow.</span>
            </div>
            <div className="service-modal-actions">
              <button className="secondary-btn" onClick={() => setSelected(null)}>Close</button>
              <button className="primary-btn" onClick={() => setSelected(null)}>Continue to portal →</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
