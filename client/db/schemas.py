from pydantic import BaseModel


class Event(BaseModel):
    event_uuid: str
    value: float
    unit: str
    sensor_uuid: str
    transmitted: bool

    class Config:
        orm_mode = True


class Sensor(BaseModel):
    sensor_uuid: str
    sensor_type: str
    sensor_name: str

    class Config:
        orm_mode = True


class Averages(BaseModel):
    average_uuid: str
    sensor_uuid: str
    average: int

    class Config:
        orm_mode = True
