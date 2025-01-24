import logging
from sqlalchemy import Column, Integer, String
from bot.db import Base

logger = logging.getLogger(__name__)

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, index=True)
    username = Column(String, index=True, nullable=True)

    def __repr__(self):
        return f"<Employee user_id={self.user_id}, username={self.username}>"
