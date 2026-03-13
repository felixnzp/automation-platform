from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: LoginRequest):
    if payload.username == "admin" and payload.password == "admin123":
        return {"token": "fake-jwt-token"}
    raise HTTPException(status_code=401, detail="Invalid username or password")
