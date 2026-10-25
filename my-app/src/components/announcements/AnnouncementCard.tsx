
type Announcement = {
  id: string;
  title: string;
  text: string;
  tag: string;
  date: string;
  read?: boolean;
};

type Props = {
  announcement: Announcement;
  onOpen: (announcement: Announcement) => void;
};

export default function AnnouncementCard({ announcement, onOpen }: Props) {
  return (
    <article className={`announcement-card ${announcement.read ? 'read' : 'unread'}`}>
      <div className="announcement-card-top">
        <span className={`tag ${announcement.tag === 'Important' ? 'important' : ''}`}>
          {announcement.tag}
        </span>
        <span className="announcement-date">{announcement.date}</span>
      </div>
      <h2>{announcement.title}</h2>
      <p>{announcement.text}</p>
      <button className="text-btn" type="button" onClick={() => onOpen(announcement)}>
        Read announcement →
      </button>
    </article>
  );
}
