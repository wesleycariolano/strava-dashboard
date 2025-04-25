from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Athlete(Base):
    __tablename__ = "athletes"
    id = Column(Integer, primary_key=True)
    strava_id = Column(Integer, unique=True, nullable=False)
    firstname = Column(String)
    lastname = Column(String)
    profile_picture = Column(String)  # url da foto do strava
    access_token = Column(String)
    refresh_token = Column(String)
    token_expires_at = Column(Integer)
    last_activities_update = Column(DateTime, default=datetime(2000,1,1))

    activities = relationship("Activity", back_populates="athlete")

class Activity(Base):
    __tablename__ = "activities"
    id = Column(Integer, primary_key=True)
    strava_id = Column(Integer, unique=True, nullable=False)
    athlete_id = Column(Integer, ForeignKey('athletes.id'))
    name = Column(String)
    type = Column(String)  # Run, Walk, etc
    distance = Column(Float)  # metros
    moving_time = Column(Integer)
    elapsed_time = Column(Integer)
    start_date = Column(DateTime)
    start_date_local = Column(DateTime)

    athlete = relationship("Athlete", back_populates="activities")

    __table_args__ = (UniqueConstraint('strava_id', name='_strava_id_uc'),)