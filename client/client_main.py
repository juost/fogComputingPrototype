import math
import random
import asyncio
import uuid
from datetime import datetime

from sqlalchemy import insert, select, update
from client.generated.fast_api_client.client import Client
from client.generated.fast_api_client.api.default import (
    create_sensor_create_sensor_post as createSensor,
    post_sensor_data_sensordata_post as postSensorData,
    post_received_averages_received_averages_post as postReceivedAverages
)
from client.generated.fast_api_client.models import SensorRegisterRemote, SensorRemote, SensorEventDataRequest, \
    EventRemote, AverageReceivedAck
from client.db import database, models

client = Client("http://localhost:8000")


# AI generated temperature simulation code
def generate_temperature(base_temp=22.0):
    """Generate realistic temperature values with a diurnal cycle and noise."""
    current_time = datetime.now()
    seconds_in_day = 24 * 60 * 60
    time_fraction = (current_time.hour * 3600 + current_time.minute * 60 + current_time.second) / seconds_in_day
    diurnal_variation = 10 * math.sin(2 * math.pi * time_fraction)  # +/- 10 degrees variation
    noise = random.uniform(-1.0, 1.0)  # small random noise
    return base_temp + diurnal_variation + noise


# AI generated humidity simulation code
def generate_humidity(base_humidity=50.0):
    """Generate realistic humidity values with a daily cycle and noise."""
    current_time = datetime.now()
    seconds_in_day = 24 * 60 * 60
    time_fraction = (current_time.hour * 3600 + current_time.minute * 60 + current_time.second) / seconds_in_day
    diurnal_variation = -10 * math.sin(2 * math.pi * time_fraction)  # +/- 10% variation (inverse of temperature)
    noise = random.uniform(-2.0, 2.0)  # small random noise
    return base_humidity + diurnal_variation + noise


async def postDataPeriodically(periodInSecs: int):
    while True:
        try:
            await asyncio.sleep(periodInSecs)
            print("Sending latest sensor data")
            async with database.SessionLocal() as session:
                ## fill input with untransmitted events from db
                async with session.begin():
                    result = await session.execute(
                        select(models.Event)
                        .where(models.Event.transmitted == False)
                    )
                events = result.scalars().all()
                events = [EventRemote(
                    event_uuid=event.event_uuid,
                    value=event.value,
                    unit=event.unit,
                    sensor_uuid=event.sensor_uuid,
                    timestamp=event.time.isoformat()
                ) for event in events]
                r = await postSensorData.asyncio(
                    client=client,
                    body=SensorEventDataRequest(
                        events=events
                    )
                )
                # mark r.received_event_uuids in db as transmitted
                for event in r.received_event_uuids:
                    async with session.begin():
                        await session.execute(
                            update(models.Event)
                            .where(models.Event.event_uuid == event)
                            .values(transmitted=True)
                        )
                # save r.averages to db
                for avg in r.averages:
                    async with session.begin():
                        session.add(models.Averages(
                            average_uuid=avg.average_uuid,
                            average=avg.average,
                            calculation_timestamp=datetime.fromisoformat(avg.average_timestamp),
                            sensor_uuid=avg.sensor_uuid
                        ))
                receivedUuids = [x.average_uuid for x in r.averages]
                await postReceivedAverages.asyncio(
                    client=client,
                    body=AverageReceivedAck(
                        received=receivedUuids
                    )
                )
        except Exception as e:
            print("Failed to communicate with server:", str(e))


async def generateSensorData(sensor: models.Sensor, value_generator: callable, unit: str):
    while True:
        async with database.SessionLocal() as session:
            async with session.begin():
                session.add(models.Event(
                    sensor_uuid=sensor.sensor_uuid,
                    event_uuid=uuid.uuid4().hex,
                    value=value_generator(),
                    time=datetime.now(),
                    unit=unit,
                    transmitted=False
                ))
        await asyncio.sleep(random.uniform(1, 3))


async def registerSensorOnServer(sensor_type: str, sensor_name: str) -> SensorRemote:
    print("Registering sensor on server:", sensor_name)
    return await createSensor.asyncio(
        client=client,
        body=SensorRegisterRemote(
            type=sensor_type,
            name=sensor_name
        )
    )


async def storeSensorToDb(sensor: SensorRemote):
    print("Storing new sensor to db:", sensor.name)
    async with database.SessionLocal() as session:
        async with session.begin():
            session.add(models.Sensor(
                sensor_uuid=sensor.uuid,
                sensor_type=sensor.type,
                sensor_name=sensor.name
            ))


def convert_sensor_remote_to_sensor(sensor_remote: SensorRemote) -> models.Sensor:
    return models.Sensor(
        sensor_uuid=sensor_remote.uuid,
        sensor_type=sensor_remote.type,
        sensor_name=sensor_remote.name
    )


async def getSensor(sensor_type: str, sensor_name: str) -> models.Sensor:
    async with database.SessionLocal() as session:
        result = await session.execute(
            select(models.Sensor)
            .where(models.Sensor.sensor_type == sensor_type, models.Sensor.sensor_name == sensor_name)
        )
        tempSensorRow = result.first()
        if tempSensorRow:
            print("Found sensor in db:", sensor_name)
            return tempSensorRow[0]
        sensor = await registerSensorOnServer(sensor_type=sensor_type, sensor_name=sensor_name)
        await storeSensorToDb(sensor)
        return convert_sensor_remote_to_sensor(sensor)


async def create_tables():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


async def run():
    await create_tables()
    temp_sensor = await getSensor("temperature", "temp_sensor")
    hum_sensor = await getSensor("humidity", "hum_sensor")
    await asyncio.gather(
        generateSensorData(temp_sensor, generate_temperature, "degree"),
        generateSensorData(hum_sensor, generate_humidity, "percent"),
        postDataPeriodically(15)
    )


if __name__ == "__main__":
    asyncio.run(run())
