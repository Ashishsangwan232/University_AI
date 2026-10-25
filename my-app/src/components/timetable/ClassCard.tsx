
type ClassCardProps = {
  time: string;
  subject: string;
  faculty: string;
  room: string;
  status?: 'completed' | 'current' | 'upcoming';
};

export default function ClassCard({ time, subject, faculty, room, status = 'upcoming' }: ClassCardProps) {
  return (
    <article className={`class-card ${status}`}>
      <div className="class-time">{time}</div>
      <div className="class-main">
        <div className="class-title-row">
          <h3>{subject}</h3>
          {status === 'current' && <span className="class-status">Now</span>}
          {status === 'completed' && <span className="class-status muted-status">Done</span>}
        </div>
        <p>{faculty}</p>
        <span className="class-room">{room}</span>
      </div>
    </article>
  );
}
