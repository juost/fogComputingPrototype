from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Float

from client.db.database import Base


class Event(Base):
    __tablename__ = "events"
    event_uuid = Column(String, primary_key=True)
    value = Column(Float)
    unit = Column(String)
    transmitted = Column(Boolean)
    sensor_uuid = Column(String, ForeignKey("sensors.sensor_uuid"))


class Sensor(Base):
    __tablename__ = "sensors"
    sensor_uuid = Column(String, primary_key=True)
    sensor_type = Column(String)
    sensor_name = Column(String)


class Averages(Base):
    __tablename__ = "averages"
    average_uuid = Column(String, primary_key=True)
    average = Column(Integer)
    calculation_timestamp = Column(DateTime)
    sensor_uuid = Column(String, ForeignKey("sensors.sensor_uuid"))
