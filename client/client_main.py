import random
import time

from sqlalchemy import insert

import generated.fast_api_client.client as client
import generated.fast_api_client.api.default.get_sensors_sensors_get as getSensors
import generated.fast_api_client.api.default.post_sensor_data_sensordata_post as postSensorData
import generated.fast_api_client.api.default.post_received_averages_received_averages_post as postReceivedAverages
import asyncio

# from db import database, models
import client.db.database as database
import client.db.models as models
from generated.fast_api_client.models import SensorEventDataRequest, EventRemote, AverageReceivedAck


def generate_temperature():
    return round(random.uniform(20.0, 30.0), 2)


def generate_humidity():
    return round(random.uniform(30.0, 70.0), 2)


async def postDataPeriodocally(perionInSecs: int):
    while True:
        print("Posting latest sensor data")
        ## fill input with untransimtted events from db
        r = await postSensorData.asyncio(
            client=client,
            body=SensorEventDataRequest(
                sensor_uuid="",
                events=[
                    EventRemote(
                        event_uuid="abc",
                        value=21,
                        unit="degree"
                    )
                ]
            )
        )
        # mark r.received_event_uuids in db as transmitted
        # save r.averages to db
        receivedUuids = map(lambda x: x.average_uuid, r.averages)
        await postReceivedAverages.asyncio(
            client=client,
            body=AverageReceivedAck(
                received_event_uuids=list(receivedUuids)
            )
        )
        time.sleep(perionInSecs)


async def generateSensorData():
    while True:
        temp = generate_temperature()
        humidity = generate_humidity()
        ## write events to db
        database.SessionLocal().execute(insert(models.Event).values(
            sensor_uuid="temp_sensor",
            value=temp,
            unit="degree",
            transmitted=False
            )
        )
        # database.SessionLocal().execute(insert(models.Event).values(
        #     sensor_uuid="hum_sensor",
        #     value=humidity,
        #     unit="percent",
        #     transmitted=False
        #     )
        # )
        time.sleep(0.33)


if __name__ == "__main__":
    models.Base.metadata.create_all(bind=database.engine)
    database.SessionLocal().execute(insert(models.Sensor).values(
        sensor_uuid="temp_sensor",
        sensor_type="temperature",
        sensor_name="Temperature Sensor"
    )
    )
    client = client.Client("http://localhost:8000")
    asyncio.run(generateSensorData())
    asyncio.run(postDataPeriodocally(20))
