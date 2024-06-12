from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base


class Event(Base):
    __tablename__ = "event_data"
    event_uuid = Column(String, primary_key=True)
    value = Column(Integer)
    unit = Column(String)
    sensor_uuid = Column(String, ForeignKey("sensor_data.sensor_uuid"))
    sensor = relationship("Sensor", back_populates="events")

class Sensor(Base):
    __tablename__ = "sensor_data"
    sensor_uuid = Column(String, primary_key=True)
    sensor_type = Column(String)
    sensor_name = Column(String)
    events = relationship("Event", back_populates="sensor")
