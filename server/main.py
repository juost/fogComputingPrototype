import asyncio
import functools
import os
import uuid
from datetime import datetime
from typing import List

import sqlalchemy
import uvicorn
from fastapi import FastAPI, Request, Response, Depends, Query
from sqlalchemy import insert, update, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from starlette.responses import HTMLResponse
from starlette.websockets import WebSocket

import db.models as models
import db.database as database

from db import schemas

import apimodels

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


async def create_tables():
    async with database.engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    response = Response("Internal server error", status_code=500)
    try:
        request.state.db = database.SessionLocal()
        response = await call_next(request)
    finally:
        await request.state.db.close()
    return response


async def get_db(request: Request):
    async with request.state.db as session:
        yield session


@app.get("/", tags=["root"])
async def read_root() -> HTMLResponse:
    filePath = os.path.join(BASE_DIR, 'index.html')
    with open(filePath) as f:
        return HTMLResponse(f.read())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, sensor_uuid: str = Query(...)):
    await websocket.accept()
    dbSession = database.SessionLocal()
    try:
        while True:
            result = await dbSession.execute(
                select(models.Event)
                .where(models.Event.sensor_uuid == sensor_uuid)
                .order_by(models.Event.timestamp.desc())
            )
            result_list = result.fetchall()
            result_dict = [{"timestamp": row.Event.timestamp.isoformat(), "value": row.Event.value} for row in
                           result_list]

            # Fetch averages data
            averages = await dbSession.execute(
                select(models.Averages)
                .where(models.Averages.sensor_uuid == sensor_uuid)
                .order_by(models.Averages.calculation_timestamp.desc())
            )
            averages_list = averages.fetchall()
            averages_dict = [
                {"timestamp": row.Averages.calculation_timestamp.isoformat(), "value": row.Averages.average,
                 "transmitted": row.Averages.transmitted} for row in averages_list]

            await websocket.send_json({"events": result_dict, "averages": averages_dict})
            await asyncio.sleep(2)
    except Exception as e:
        print("Websocket connection error: " + str(e))
    finally:
        try:
            await websocket.close()
        except Exception as e:
            pass
        await dbSession.close()
        print("Websocket connection closed")


@app.get("/sensors", response_model=list[schemas.Sensor])
async def getSensors(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Sensor).offset(skip).limit(limit))
    return result.scalars().all()


@app.post("/createSensor", response_model=apimodels.SensorRemote)
async def createSensor(newSensor: apimodels.SensorRegisterRemote, db: AsyncSession = Depends(get_db)):
    sensor_uuid = uuid.uuid4().hex
    await db.execute(
        insert(models.Sensor).values(
            sensor_uuid=sensor_uuid,
            sensor_type=newSensor.type,
            sensor_name=newSensor.name
        )
    )
    await db.commit()
    return apimodels.SensorRemote(uuid=sensor_uuid, type=newSensor.type, name=newSensor.name)


@app.post("/receivedAverages")
async def postReceivedAverages(received: apimodels.AverageReceivedAck, db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(models.Averages)
        .where(models.Averages.average_uuid.in_(received.received))
        .values(transmitted=True)
    )
    await db.commit()
    return {"message": "Received averages updated"}


@app.post("/sensordata", response_model=apimodels.AveragesResponse)
async def postSensorData(request: apimodels.SensorEventDataRequest, db: AsyncSession = Depends(get_db)):
    ## insert data into database
    for event in request.events:
        time = datetime.fromisoformat(event.timestamp)
        try:
            await db.execute(
                insert(models.Event).values(
                    event_uuid=event.event_uuid,
                    value=event.value,
                    unit=event.unit,
                    sensor_uuid=event.sensor_uuid,
                    timestamp=time
                )
            )
        # ignore retransmitted events
        except sqlalchemy.exc.IntegrityError as e:
            pass
    await db.commit()
    #find all sensor uuids in request
    sensor_uuids = list(set([event.sensor_uuid for event in request.events]))
    # for each sensor uuid, calculate average and store in database
    for sensor_uuid in sensor_uuids:
        result = await db.execute(
            select(models.Event)
            .where(models.Event.sensor_uuid == sensor_uuid)
            .order_by(models.Event.timestamp.desc()).limit(10)
        )
        last10values = result.scalars().all()

        if len(last10values) == 0:
            continue

        avg = functools.reduce(lambda x, y: x + y, map(lambda x: x.value, last10values)) / len(last10values)

        await db.execute(
            insert(models.Averages).values(
                average_uuid=uuid.uuid4().hex,
                sensor_uuid=sensor_uuid,
                calculation_timestamp=datetime.now(),
                average=avg,
                transmitted=False
            )
        )

    await db.commit()

    # get all untransmitted averages for sensors in request
    items = await db.execute(
        select(models.Averages)
        .where(models.Averages.transmitted == False, models.Averages.sensor_uuid.in_(sensor_uuids))
    )
    averages = items.scalars().all()

    # map to remote model
    avgsRemote = [
        apimodels.AverageRemote(
            average=average.average,
            average_uuid=average.average_uuid,
            average_timestamp=average.calculation_timestamp.isoformat(),
            sensor_uuid=average.sensor_uuid
        )
        for average in averages
    ]
    return apimodels.AveragesResponse(averages=avgsRemote,
                                      received_event_uuids=[event.event_uuid for event in request.events])


if __name__ == "__main__":
    asyncio.run(create_tables())
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
