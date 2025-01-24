import logging
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from bot.db import Base

logger = logging.getLogger(__name__)

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True)
    event_id = Column(String, index=True)
    title = Column(String)

    # Храним start_time/end_time в "naive UTC" (тип просто DateTime)
    start_time = Column(DateTime)
    end_time = Column(DateTime)

    is_taken = Column(Boolean, default=False)
    taken_by = Column(String, nullable=True)

    # Флаг для учёта «технической встречи»
    is_technical = Column(Boolean, default=False)

    def __repr__(self):
        return (
            f"<Event event_id={self.event_id}, title={self.title}, "
            f"is_technical={self.is_technical}>"
        )
