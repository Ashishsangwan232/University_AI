from pydantic import BaseModel


class StudentProfile(BaseModel):
    """The student CampusAI is acting for.

    Everything except ``id`` and ``name`` is optional, because UMS is the source
    of truth and it does not put a programme or a year on the dashboard. A field
    that could not be read comes back absent rather than invented, and ``live``
    says which of the two sources this record came from.
    """

    id: str
    name: str
    program: str | None = None
    department: str | None = None
    year: int | None = None
    semester: int | None = None
    #: Registration number as UMS prints it (its "VID").
    student_id: str | None = None
    section: str | None = None
    term: str | None = None
    hostel: str | None = None
    room: str | None = None
    portal_connected: bool = False
    #: True when this came from the authenticated UMS session.
    live: bool = False
    source: str = ""
    #: Which UMS reading produced the name - useful when it looks wrong.
    name_source: str | None = None
