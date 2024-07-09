from pydantic import BaseModel


class SensorRemote(BaseModel):
    uuid: str
    type: str
    name: str

class SensorRegisterRemote(BaseModel):
    type: str
    name: str


class EventRemote(BaseModel):
    event_uuid: str
    value: float
    unit: str
    timestamp: str
    sensor_uuid: str


class SensorEventDataRequest(BaseModel):
    events: list[EventRemote]


class AverageRemote(BaseModel):
    average: float
    average_uuid: str
    average_timestamp: str
    sensor_uuid: str


class AveragesResponse(BaseModel):
    averages: list[AverageRemote]
    received_event_uuids: list[str]


class AverageReceivedAck(BaseModel):
    received: list[str]
