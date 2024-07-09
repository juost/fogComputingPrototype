import argparse
import math
import random
import asyncio
import uuid
from datetime import datetime

import pytz
from matplotlib import pyplot as plt
from matplotlib.dates import DateFormatter
from sqlalchemy import insert, select, update

# Fix for matplotlib not updating
import matplotlib

matplotlib.use("Qt5Agg")

import sys
import os
# Ensure the parent directory is in the path --> fix import issues
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.generated.fast_api_client.client import Client
from client.generated.fast_api_client.api.default import (
    create_sensor_create_sensor_post as createSensor,
    post_sensor_data_sensordata_post as postSensorData,
    post_received_averages_received_averages_post as postReceivedAverages
)
from client.generated.fast_api_client.models import SensorRegisterRemote, SensorRemote, SensorEventDataRequest, \
    EventRemote, AverageReceivedAck
from client.db import database, models

# Argument parsing
parser = argparse.ArgumentParser(description="Client for connecting to the cloud server.")
parser.add_argument("--server-ip", type=str, required=True, help="The IP address of the cloud server.")
parser.add_argument("--server-port", type=int, required=False, help="The IP address of the cloud server.", default=8000)
args = parser.parse_args()

client = Client(f"http://{args.server_ip}:{args.server_port}")


# Data generation functions
async def generate_sensor_data(sensor: models.Sensor, value_generator: callable, unit: str):
    while True:
        async with database.SessionLocal() as session:
            async with session.begin():
                session.add(models.Event(
                    sensor_uuid=sensor.sensor_uuid,
                    event_uuid=uuid.uuid4().hex,
                    value=value_generator(),
                    time=datetime.now(pytz.UTC),
                    unit=unit,
                    transmitted=False
                ))
        await asyncio.sleep(random.uniform(1, 3))


async def periodical_cloud_sync(period_in_secs: int):
    while True:
        try:
            await asyncio.sleep(period_in_secs)
            print("Sending untransmitted sensor data to cloud server")
            async with database.SessionLocal() as session:
                async with session.begin():
                    event_query_result = await session.execute(
                        select(models.Event)
                        .where(models.Event.transmitted == False)
                    )
                events = event_query_result.scalars().all()
                events = [EventRemote(
                    event_uuid=event.event_uuid,
                    value=event.value,
                    unit=event.unit,
                    sensor_uuid=event.sensor_uuid,
                    timestamp=event.time.isoformat()
                ) for event in events]
                sensor_data_response = await postSensorData.asyncio(
                    client=client,
                    body=SensorEventDataRequest(
                        events=events
                    )
                )
                # mark sensor_data_response.received_event_uuids in db as transmitted
                async with session.begin():
                    await session.execute(
                        update(models.Event)
                        .where(models.Event.event_uuid.in_(sensor_data_response.received_event_uuids))
                        .values(transmitted=True)
                    )

                # save sensor_data_response.averages to db
                for avg in sensor_data_response.averages:
                    async with session.begin():
                        # ignore on conflict in case of retransmitted averages because of lost acks
                        stmt = insert(models.Averages).values(
                            average_uuid=avg.average_uuid,
                            average=avg.average,
                            calculation_timestamp=datetime.fromisoformat(avg.average_timestamp).astimezone(pytz.UTC),
                            sensor_uuid=avg.sensor_uuid
                        ).prefix_with("OR IGNORE")
                        await session.execute(stmt)
                received_uuids = [x.average_uuid for x in sensor_data_response.averages]
                await postReceivedAverages.asyncio(
                    client=client,
                    body=AverageReceivedAck(
                        received=received_uuids
                    )
                )
        except Exception as e:
            print("Failed to communicate with server:", str(e))


# Sensor registration functions
async def register_sensor_on_server(sensor_type: str, sensor_name: str) -> SensorRemote:
    print("Registering sensor on server:", sensor_name)
    return await createSensor.asyncio(
        client=client,
        body=SensorRegisterRemote(
            type=sensor_type,
            name=sensor_name
        )
    )


async def store_sensor_to_db(sensor: SensorRemote):
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


async def get_sensor(sensor_type: str, sensor_name: str) -> models.Sensor:
    async with database.SessionLocal() as session:
        result = await session.execute(
            select(models.Sensor)
            .where(models.Sensor.sensor_type == sensor_type, models.Sensor.sensor_name == sensor_name)
        )
        temp_sensor_row = result.first()
        if temp_sensor_row:
            print("Found sensor in db:", sensor_name)
            return temp_sensor_row[0]
        sensor = await register_sensor_on_server(sensor_type=sensor_type, sensor_name=sensor_name)
        await store_sensor_to_db(sensor)
        return convert_sensor_remote_to_sensor(sensor)


# Plot functions
async def plots(tempSensor, humSensor):
    plt.ion()
    fig, ax1, ax2, temp_transmitted_line, temp_non_transmitted_line, temp_avg_line, hum_transmitted_line, hum_non_transmitted_line, hum_avg_line = initialize_plots()
    while True:
        async with database.SessionLocal() as session:
            temp_events = await session.execute(
                select(models.Event).where(models.Event.sensor_uuid == tempSensor.sensor_uuid))
            temp_averages = await session.execute(
                select(models.Averages).where(models.Averages.sensor_uuid == tempSensor.sensor_uuid))
            temp_events = temp_events.scalars().all()
            temp_averages = temp_averages.scalars().all()

            hum_events = await session.execute(
                select(models.Event).where(models.Event.sensor_uuid == humSensor.sensor_uuid))
            hum_averages = await session.execute(
                select(models.Averages).where(models.Averages.sensor_uuid == humSensor.sensor_uuid))
            hum_events = hum_events.scalars().all()
            hum_averages = hum_averages.scalars().all()

        update_plot(ax1, temp_transmitted_line, temp_non_transmitted_line, temp_avg_line, temp_events, temp_averages)
        update_plot(ax2, hum_transmitted_line, hum_non_transmitted_line, hum_avg_line, hum_events, hum_averages)
        plt.pause(0.01)
        await asyncio.sleep(5)


def initialize_plots():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))
    fig.suptitle('Client', fontsize=16)
    # Temperature plot
    ax1.set_title('Temperature Sensor Data')
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Value')
    ax1.grid(True)
    ax1.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))

    temp_transmitted_line, = ax1.plot([], [], label='Transmitted Events', marker='o')
    temp_non_transmitted_line, = ax1.plot([], [], label='Non-Transmitted Events', linestyle='dotted', marker='o')
    temp_avg_line, = ax1.plot([], [], label='Averages', marker='x')
    ax1.legend()

    # Humidity plot
    ax2.set_title('Humidity Sensor Data')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Value')
    ax2.grid(True)
    ax2.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))

    hum_transmitted_line, = ax2.plot([], [], label='Transmitted Events', marker='o')
    hum_non_transmitted_line, = ax2.plot([], [], label='Non-Transmitted Events', linestyle='dotted', marker='o')
    hum_avg_line, = ax2.plot([], [], label='Averages', marker='x')
    ax2.legend()

    plt.tight_layout()
    return fig, ax1, ax2, temp_transmitted_line, temp_non_transmitted_line, temp_avg_line, hum_transmitted_line, hum_non_transmitted_line, hum_avg_line


def update_plot(ax, transmitted_line, non_transmitted_line, avg_line, events: list[models.Event],
                averages: list[models.Averages]):
    avg_times = [avg.calculation_timestamp for avg in averages]
    avg_values = [avg.average for avg in averages]

    transmitted_times = [event.time for event in events if event.transmitted]
    transmitted_values = [event.value for event in events if event.transmitted]
    non_transmitted_times = [event.time for event in events if not event.transmitted]
    non_transmitted_values = [event.value for event in events if not event.transmitted]

    transmitted_line.set_data(transmitted_times, transmitted_values)
    non_transmitted_line.set_data(non_transmitted_times, non_transmitted_values)
    avg_line.set_data(avg_times, avg_values)

    ax.relim()
    ax.autoscale_view()
    ax.figure.canvas.draw()
    ax.figure.canvas.flush_events()


# Table creation function
async def create_tables():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


# AI generated sensor value simulation code

# Initialize starting points for temperature and humidity
current_temperature = 22.0
current_humidity = 50.0


def generate_temperature(variation=0.05, noise_level=0.5, min_temp=-10.0, max_temp=45.0):
    """Generate realistic temperature values with gradual changes and some noise."""
    global current_temperature
    current_time = datetime.now(pytz.UTC)
    seconds_in_day = 24 * 60 * 60
    time_fraction = (current_time.hour * 3600 + current_time.minute * 60 + current_time.second) / seconds_in_day
    diurnal_variation = 10 * math.sin(2 * math.pi * time_fraction)  # +/- 10 degrees variation
    noise = random.uniform(-noise_level, noise_level)  # small random noise
    # Gradual change
    current_temperature += random.uniform(-variation, variation)
    # Clip the temperature value to be within given bounds
    current_temperature = max(min(current_temperature, max_temp), min_temp)
    return diurnal_variation + current_temperature + noise


def generate_humidity(variation=0.1, noise_level=1.0, min_humidity=5.0, max_humidity=95.0):
    """Generate realistic humidity values with gradual changes and some noise."""
    global current_humidity
    current_time = datetime.now(pytz.UTC)
    seconds_in_day = 24 * 60 * 60
    time_fraction = (current_time.hour * 3600 + current_time.minute * 60 + current_time.second) / seconds_in_day
    diurnal_variation = -10 * math.sin(2 * math.pi * time_fraction)  # +/- 10% variation (inverse of temperature)
    noise = random.uniform(-noise_level, noise_level)  # small random noise
    # Gradual change
    current_humidity += random.uniform(-variation, variation)
    # Clip the humidity value to be within given bounds
    current_humidity = max(min(current_humidity, max_humidity), min_humidity)

    return diurnal_variation + current_humidity + noise


# Main functions
async def run():
    await create_tables()
    try:
        temp_sensor = await get_sensor("temperature", "temp_sensor")
        hum_sensor = await get_sensor("humidity", "hum_sensor")
    except Exception as e:
        print("Failed to register sensors, server must be available for initial setup", str(e))
        return

    await asyncio.gather(
        generate_sensor_data(temp_sensor, generate_temperature, "degree"),
        generate_sensor_data(hum_sensor, generate_humidity, "percent"),
        periodical_cloud_sync(15),
        plots(temp_sensor, hum_sensor)
    )


if __name__ == "__main__":
    asyncio.run(run())
