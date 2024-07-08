import asyncio
import functools
import os
import uuid
from datetime import datetime
from typing import List, Any

import sqlalchemy
import uvicorn

from fastapi import FastAPI, Request, Response, Depends, Query
from sqlalchemy import insert, update, select, Result, text
from sqlalchemy.orm import Session
from starlette.responses import HTMLResponse
from starlette.websockets import WebSocket

import db.models as models
import db.database as database

from db import schemas

import apimodels

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    response = Response("Internal server error", status_code=500)
    try:
        request.state.db = database.SessionLocal()
        response = await call_next(request)
    finally:
        request.state.db.close()
    return response


def get_db(request: Request):
    return request.state.db


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
            dbSession.expire_all()
            result = dbSession.execute(
                select(models.Event)
                .where(models.Event.sensor_uuid == sensor_uuid)
                .order_by(models.Event.timestamp.desc())
            ).fetchall()
            result_dict = [{"timestamp": row.Event.timestamp.isoformat(), "value": row.Event.value} for row in result]

            # Fetch averages data
            averages = dbSession.execute(
                select(models.Averages)
                .where(models.Averages.sensor_uuid == sensor_uuid)
                .order_by(models.Averages.calculation_timestamp.desc())
            ).fetchall()
            averages_dict = [{"timestamp": row.Averages.calculation_timestamp.isoformat(), "value": row.Averages.average,
                              "transmitted": row.Averages.transmitted} for row in averages]

            await websocket.send_json({"events": result_dict, "averages": averages_dict})
            await asyncio.sleep(2)
    except Exception as e:
        print("Websocket connection error: " + e.__str__())
    finally:
        try:
            await websocket.close()
        except Exception as e:
            pass
        dbSession.close()
        print("Websocket connection closed")

@app.get("/sensors", response_model=list[schemas.Sensor])
def getSensors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = db.query(models.Sensor).offset(skip).limit(limit).all()
    return items

@app.post("/createSensor", response_model=apimodels.SensorRemote)
def createSensor(newSensor: apimodels.SensorRegisterRemote, db: Session = Depends(get_db)):
    sensor_uuid = uuid.uuid4().hex
    db.execute(
        insert(models.Sensor).values(
            sensor_uuid=sensor_uuid,
            sensor_type=newSensor.type,
            sensor_name=newSensor.name
        )
    )
    db.commit()
    return apimodels.SensorRemote(uuid=sensor_uuid, type=newSensor.type, name=newSensor.name)


@app.post("/receivedAverages")
def postReceivedAverages(received: apimodels.AverageReceivedAck, db: Session = Depends(get_db)):
    ## update database to mark averages as transmitted
    db.execute(
        update(models.Averages)
        .where(models.Averages.average_uuid.in_(received.received))
        .values(transmitted=True)
    )
    db.commit()
    print("Reveiced averages: ", received)


@app.post("/sensordata", response_model=apimodels.AveragesResponse)
async def postSensorData(request: apimodels.SensorEventDataRequest, db: Session = Depends(get_db)):
    ## insert data into database
    for event in request.events:
        time = datetime.utcfromtimestamp(float(event.timestamp))
        try:
            db.execute(
                insert(models.Event).values(
                    event_uuid=event.event_uuid,
                    value=event.value,
                    unit=event.unit,
                    sensor_uuid=request.sensor_uuid,
                    timestamp=time
                )
            )
        # ignore retransmitted events
        except sqlalchemy.exc.IntegrityError as e:
            pass
    db.commit()
    #calculate the average event value of all events in request
    result = db.execute(
        select(models.Event)
        .where(models.Event.sensor_uuid == request.sensor_uuid)
        .order_by(models.Event.timestamp.desc()).limit(10)
    ).fetchall()
    last10values: list[models.Event] = [row.Event for row in result]

    if len(last10values) == 0:
        return apimodels.AveragesResponse(averages=[], received_event_uuids=[])

    avg = functools.reduce(lambda x, y: x + y, map(lambda x: x.value, last10values)) / len(last10values)

    #store avg in database
    db.execute(
        insert(models.Averages).values(
            average_uuid=uuid.uuid4().hex,
            sensor_uuid=request.sensor_uuid,
            calculation_timestamp = datetime.utcnow(),
            average=avg,
            transmitted=False
        )
    )
    db.commit()

    #get all untransmitted averages
    items = db.query(models.Averages).filter(models.Averages.transmitted == False, models.Averages.sensor_uuid == request.sensor_uuid).all()

    #map to remote model
    avgsRemote = [
        apimodels.AverageRemote(
            average=average.average,
            average_uuid=average.average_uuid,
            average_timestamp=average.calculation_timestamp.isoformat()
        )
        for average in items
    ]
    return apimodels.AveragesResponse(averages=avgsRemote, received_event_uuids=[event.event_uuid for event in request.events])


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
