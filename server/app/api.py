from fastapi import FastAPI

from db import models
from db.database import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/", tags=["root"])
async def read_root() -> dict:
    return {"test": "test"}
