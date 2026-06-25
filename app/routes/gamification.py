from fastapi import APIRouter, Header, HTTPException
from typing import Optional
from app.services import gamification_service, auth_service
from app.services.db import read_all

router = APIRouter()

def _get_user(auth_header):
    if not auth_header or " " not in auth_header:
        return None
    return auth_service.get_current_user(auth_header.split(" ",1)[1])

@router.get("/me")
def my_stats(authorization: Optional[str] = Header(None)):
    user = _get_user(authorization)
    if not user:
        raise HTTPException(401, "Auth required")
    return gamification_service.get_user_stats(user["id"])

@router.get("/leaderboard")
def leaderboard():
    return gamification_service.get_leaderboard()

@router.get("/missions")
def missions():
    return read_all("missions")

@router.get("/badges")
def badges():
    return gamification_service.ACHIEVEMENT_BADGES

@router.get("/tiers")
def tiers():
    return [{"min_xp": t[0], "name": t[1], "icon": t[2]} for t in gamification_service.TIERS]