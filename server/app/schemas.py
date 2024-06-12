from pydantic import BaseModel


class Event(BaseModel):
    event_uuid: str
    value: int
    unit: str
    sensor_uuid: str

    class Config:
        orm_mode = True


class Sensor(BaseModel):
    sensor_uuid: str
    sensor_type: str
    sensor_name: str
    events: list[Event] = []

    class Config:
        orm_mode = True
