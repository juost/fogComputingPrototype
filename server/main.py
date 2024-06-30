import functools
import uuid

import uvicorn

from fastapi import FastAPI, Request, Response, Depends
from sqlalchemy import insert, update, select, Result
from sqlalchemy.orm import Session

import db.models as models
import db.database as database

from db import schemas

import apimodels

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()


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
async def read_root() -> dict:
    return {"test": "is working"}


@app.get("/sensors", response_model=list[schemas.Sensor])
def getSensors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = db.query(models.Sensor).offset(skip).limit(limit).all()
    return items

@app.post("/createSensor")
def getSensors(newSensor: apimodels.SensorRemote, db: Session = Depends(get_db)):
    db.execute(
        insert(models.Sensor).values(
            sensor_uuid=newSensor.uuid,
            sensor_type=newSensor.type,
            sensor_name=newSensor.name
        )
    )


@app.post("/receivedAverages")
def postReceivedAverages(received: apimodels.AverageReceivedAck, db: Session = Depends(get_db)):
    ## update database to mark averages as transmitted
    db.execute(
        update(schemas.Averages)
        .where(schemas.Averages.average_uuid.in_(received.received))
        .values(transmitted=True)
    )
    print("Reveiced averages: ", received)


@app.post("/sensordata", response_model=apimodels.AveragesResponse)
async def postSensorData(request: apimodels.SensorEventDataRequest, db: Session = Depends(get_db)):
    ## insert data into database
    for event in request.events:
        db.execute(
            insert(models.Event).values(
                event_uuid=event.event_uuid,
                value=event.value,
                unit=event.unit,
                sensor_uuid=request.sensor_uuid
            )
        )

    #calculate the average event value of all events in request
    last10values: Result[models.Event] = db.execute(
        select(models.Event)
        .where(models.Event.sensor_uuid == request.sensor_uuid)
        .order_by(models.Event.timestamp.desc()).limit(10)
    )
    avg = functools.reduce(lambda x, y: x + y, map(lambda x: x.value, last10values)) / len(request.events)


    #store avg in database
    averages = db.execute(
        insert(models.Averages).values(
            average_uuid=uuid.uuid4(),
            sensor_uuid=request.sensor_uuid,
            average=avg,
            transmitted=False
        )
    )

    #get and return all untransmitted averages
    items = db.query(models.Averages).filter(models.Averages.transmitted == False).all()
    return items


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
