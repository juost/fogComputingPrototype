from fastapi import FastAPI, HTTPException, Request, Response, Depends
from sqlalchemy.orm import Session

import app.db.models as models
import app.db.database as database

from app.db import schemas

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
