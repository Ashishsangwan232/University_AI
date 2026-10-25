from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import Base, SessionLocal, engine
from app.models import Announcement, AttendanceSubject, CollegeService, Student, TimetableClass


DEMO_STUDENT = Student(
    id="student-demo", name="Ashish Sangwan", program="B.Tech", department="CSE",
    year=3, semester=5, portal_connected=False,
)

DEMO_SUBJECTS = [
    AttendanceSubject(student_id="student-demo", name="Database Management Systems", short="DBMS", attended=32, total=40, teacher="Dr. Mehta"),
    AttendanceSubject(student_id="student-demo", name="Operating Systems", short="OS", attended=35, total=45, teacher="Dr. Sharma"),
    AttendanceSubject(student_id="student-demo", name="Computer Networks", short="CN", attended=28, total=32, teacher="Prof. Singh"),
    AttendanceSubject(student_id="student-demo", name="Mathematics", short="MATH", attended=30, total=40, teacher="Dr. Kapoor"),
]

DEMO_CLASSES = [
    ("Monday", "09:00", "10:00", "Computer Networks", "Room 204", "Dr. Kapoor"),
    ("Monday", "10:15", "11:15", "Database Management Systems", "Lab 3", "Dr. Mehta"),
    ("Monday", "11:30", "12:30", "Mathematics", "Room 118", "Dr. Kapoor"),
    ("Tuesday", "09:00", "10:00", "Operating Systems", "Room 205", "Dr. Sharma"),
    ("Tuesday", "10:15", "11:15", "Computer Networks", "Room 204", "Dr. Singh"),
    ("Wednesday", "09:00", "10:00", "Database Management Systems", "Lab 3", "Dr. Mehta"),
    ("Wednesday", "11:30", "12:30", "Operating Systems", "Room 205", "Dr. Sharma"),
    ("Thursday", "10:15", "11:15", "Mathematics", "Room 118", "Dr. Kapoor"),
    ("Thursday", "14:00", "15:00", "Computer Networks", "Room 204", "Dr. Singh"),
    ("Friday", "09:00", "10:00", "Operating Systems", "Room 205", "Dr. Sharma"),
]

DEMO_ANNOUNCEMENTS = [
    ("Mid-semester examination registration", "Sep 15", "Important", "Complete your examination registration before September 15.", True),
    ("Department seminar — AI in Healthcare", "Sep 12", "CSE", "A department seminar is scheduled for Friday at 11:00 AM in Seminar Hall 2.", False),
    ("Hostel maintenance notice", "Sep 10", "Hostel", "Routine maintenance will take place in Blocks B and C from 10 AM to 2 PM.", False),
]

DEMO_SERVICES = [
    ("Examination Registration", "Examinations", "Register for examinations and view registration requirements.", "Examination Cell", "Available", "Open service"),
    ("Fee Payment", "Finance", "View fee details and payment information.", "Accounts Office", "Available", "Open service"),
    ("Hostel Leave", "Accommodation", "Apply for hostel leave through the connected student portal.", "Hostel Office", "Portal", "Open leave"),
    ("Bonafide Certificate", "Certificates", "Request a bonafide certificate from the college office.", "Administrative Block", "Available", "Request certificate"),
    ("Academic Calendar", "Academics", "View semester dates, holidays, and academic events.", "Academic Office", "Available", "View calendar"),
    ("IT Support", "Support", "Get help with college systems and student portal access.", "IT Help Desk", "Available", "Contact support"),
]


def seed_demo_data(db: Session) -> None:
    student = db.get(Student, DEMO_STUDENT.id)
    if student is None:
        db.add(DEMO_STUDENT)
        db.flush()

    if not db.scalars(select(AttendanceSubject).where(AttendanceSubject.student_id == DEMO_STUDENT.id)).first():
        db.add_all(DEMO_SUBJECTS)

    if not db.scalars(select(TimetableClass)).first():
        db.add_all([TimetableClass(student_id="student-demo", day=day, time=time, end=end, subject=subject, room=room, teacher=teacher)
                    for day, time, end, subject, room, teacher in DEMO_CLASSES])

    if not db.scalars(select(Announcement)).first():
        db.add_all([Announcement(title=title, date=date, tag=tag, text=text, important=important)
                    for title, date, tag, text, important in DEMO_ANNOUNCEMENTS])

    if not db.scalars(select(CollegeService)).first():
        db.add_all([CollegeService(name=name, category=category, description=description, location=location, status=status, action=action)
                    for name, category, description, location, status, action in DEMO_SERVICES])

    db.commit()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)
