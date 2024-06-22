from pydantic import BaseModel


class EventRemote(BaseModel):
    event_uuid: str
    value: int
    unit: str


class SensorEventDataRequest(BaseModel):
    sensor_uuid: str
    events: list[EventRemote]


class AverageRemote(BaseModel):
    average: int
    average_uuid: str
    average_timestamp: str


class AveragesResponse(BaseModel):
    averages: list[AverageRemote]
    received_event_uuids: list[str]


class AverageReceivedAck(BaseModel):
    received: list[str]
