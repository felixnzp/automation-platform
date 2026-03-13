from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth_api import router as auth_router
from app.api.device_api import router as device_router
from app.api.task_api import router as task_router
from app.database.database import Base, engine
from app.utils.logger import system_logger

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Automation Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(device_router)
app.include_router(task_router)


@app.get("/")
def root():
    system_logger.info("health check")
    return {"message": "automation platform backend is running"}
