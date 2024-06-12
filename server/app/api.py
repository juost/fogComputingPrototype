from fastapi import FastAPI

import app.models as models
import app.database as database

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

@app.get("/", tags=["root"])
async def read_root() -> dict:
    return {"test": "test"}
