
type Announcement = {
  id: string;
  title: string;
  text: string;
  tag: string;
  date: string;
  read?: boolean;
};

type Props = {
  announcement: Announcement | null;
  onClose: () => void;
};

export default function AnnouncementModal({ announcement, onClose }: Props) {
  if (!announcement) return null;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <div className="announcement-modal" role="dialog" aria-modal="true" aria-labelledby="announcement-title" onMouseDown={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <span className={`tag ${announcement.tag === 'Important' ? 'important' : ''}`}>{announcement.tag}</span>
            <p className="announcement-date">{announcement.date}</p>
          </div>
          <button className="icon-btn" type="button" onClick={onClose} aria-label="Close announcement">×</button>
        </div>
        <h2 id="announcement-title">{announcement.title}</h2>
        <p className="announcement-modal-text">{announcement.text}</p>
        <div className="modal-footer">
          <button className="secondary-btn" type="button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
