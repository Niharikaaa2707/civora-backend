from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services import auth_service
from app.services.db import delete_one, find_many, delete_one as db_delete

router = APIRouter()

class RegisterRequest(BaseModel):
    name: str; email: str; password: str; phone: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str; password: str

@router.post("/register")
def register(req: RegisterRequest):
    try:
        user = auth_service.register_user(req.name, req.email, req.password, req.phone or "")
        return {"message": "Account created", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(req: LoginRequest):
    try:
        return auth_service.login_user(req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/me")
def me(authorization: Optional[str] = Header(None)):
    token = authorization.split(" ",1)[1] if authorization and " " in authorization else ""
    user  = auth_service.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {k: v for k, v in user.items() if k != "password"}

@router.delete("/delete-account")
def delete_account(authorization: Optional[str] = Header(None)):
    token = authorization.split(" ",1)[1] if authorization and " " in authorization else ""
    user  = auth_service.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # User ki saari issues delete karo
    issues = find_many("issues", reporter_id=user["id"])
    for issue in issues:
        delete_one("issues", issue["id"])
    
    # Gamification log delete karo
    logs = find_many("gamification_log", user_id=user["id"])
    for log in logs:
        delete_one("gamification_log", log["id"])
    
    # User delete karo
    delete_one("users", user["id"])
    
    return {"message": "Account deleted successfully"}