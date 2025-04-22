from sqlalchemy import Column, Integer, String
from database import Base

class Athlete(Base):
    __tablename__ = "athletes"
    id = Column(Integer, primary_key=True, index=True)
    strava_id = Column(Integer, unique=True, index=True)
    firstname = Column(String)
    lastname = Column(String)
    refresh_token = Column(String)
