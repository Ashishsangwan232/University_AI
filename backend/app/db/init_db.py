from app.db.session import Base, engine
from app import models  # noqa: F401 - registers the tables on Base


def init_db() -> None:
    """Create the chat tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)
