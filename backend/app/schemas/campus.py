from pydantic import BaseModel


class TimetableClassResponse(BaseModel):
    id: int
    day: str
    time: str
    end: str
    subject: str
    room: str
    teacher: str

    model_config = {"from_attributes": True}


class AnnouncementResponse(BaseModel):
    id: int
    title: str
    date: str
    tag: str
    text: str
    important: bool

    model_config = {"from_attributes": True}


class CollegeServiceResponse(BaseModel):
    id: int
    name: str
    category: str
    description: str
    location: str
    status: str
    action: str

    model_config = {"from_attributes": True}
