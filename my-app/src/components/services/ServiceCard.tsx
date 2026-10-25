export type Service = {
  title: string
  category: string
  icon: string
  description: string
  action: string
  connected: boolean
}

type Props = {
  service: Service
  onOpen: (service: Service) => void
}

export function ServiceCard({ service, onOpen }: Props) {
  return (
    <button className="service-card service-card-new" onClick={() => onOpen(service)}>
      <div className="service-card-top">
        <span className="service-icon">{service.icon}</span>
        <span className={`service-status ${service.connected ? 'connected' : ''}`}>
          {service.connected ? 'Connected' : 'Portal'}
        </span>
      </div>
      <small>{service.category}</small>
      <h2>{service.title}</h2>
      <p>{service.description}</p>
      <b>{service.action} →</b>
    </button>
  )
}
