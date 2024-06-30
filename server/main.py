import uvicorn

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from sqlalchemy import insert
from sqlalchemy.orm import Session

import db.models as models
import db.database as database

from db import schemas

from db import apimodels

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
    return {"test": "test"}


@app.get("/sensors", response_model=list[schemas.Sensor])
def getSensors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = db.query(models.Sensor).offset(skip).limit(limit).all()
    return items


@app.post("/receivedAverages")
def postReceivedAverages(received: apimodels.AverageReceivedAck, db: Session = Depends(get_db)):
    ## update database
    print("Reveiced averages: ", received)


@app.post("/sensordata", response_model=apimodels.AveragesResponse)
async def postSensorData(request: apimodels.SensorEventDataRequest, db: Session = Depends(get_db)):
    db.execute(insert(schemas.Averages).values(

    ))
    ## insert data into database
    ## calculate average and store in database
    ## return all untransmitted averages
    return items


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
