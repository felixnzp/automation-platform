from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.alert_api import router as alert_router
from app.api.auth_api import router as auth_router
from app.api.config_api import router as config_router
from app.api.dashboard_api import router as dashboard_router
from app.api.device_api import router as device_router
from app.api.port_query_api import router as port_query_router
from app.api.server_api import router as server_router
from app.api.task_api import router as task_router
from app.database.database import Base, engine
from app.models.server_inspection import ServerInspectionDetail  # noqa: F401
from app.models.server_switch_detect_log import ServerSwitchDetectLog  # noqa: F401
from app.services.alert_service import ensure_schema as ensure_alert_schema
from app.services.task_service import ensure_schema as ensure_task_schema
from app.services.task_service import start_schedule_worker, stop_schedule_worker
from app.utils.logger import system_logger

Base.metadata.create_all(bind=engine)
ensure_alert_schema()
ensure_task_schema()

app = FastAPI(title="安室智能 自动化运维平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(device_router)
app.include_router(server_router)
app.include_router(dashboard_router)
app.include_router(task_router)
app.include_router(config_router)
app.include_router(port_query_router)
app.include_router(alert_router)


@app.on_event("startup")
def on_startup():
    start_schedule_worker()
    system_logger.info("scheduled task worker started")


@app.on_event("shutdown")
def on_shutdown():
    stop_schedule_worker()
    system_logger.info("scheduled task worker stopped")


@app.get("/", include_in_schema=False)
def root():
    system_logger.info("root access")
    return {
        "message": "安室智能 自动化运维平台 backend is running",
        "frontend": "http://127.0.0.1:80",
        "docs": "http://127.0.0.1:8000/docs",
    }


@app.get("/health")
def health():
    system_logger.info("health check")
    return {"message": "安室智能 自动化运维平台 backend is running"}
