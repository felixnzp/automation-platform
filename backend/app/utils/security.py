from fastapi import Header, HTTPException


def require_admin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或Token无效")

    token = authorization.replace("Bearer ", "", 1).strip()
    if token != "fake-jwt-token":
        raise HTTPException(status_code=403, detail="无权限执行该操作")

    return {"username": "admin", "role": "admin"}
