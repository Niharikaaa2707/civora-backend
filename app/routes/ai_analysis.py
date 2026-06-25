from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.services import ai_service, auth_service

router = APIRouter()

def _get_user(auth_header):
    if not auth_header or " " not in auth_header:
        return None
    return auth_service.get_current_user(auth_header.split(" ", 1)[1])

class TextAnalysisRequest(BaseModel):
    description: str

@router.post("/analyze-text")
def analyze_text(req: TextAnalysisRequest, authorization: Optional[str] = Header(None)):
    user = _get_user(authorization)
    if not user:
        raise HTTPException(401, "Auth required")
    return ai_service.analyze_text(req.description)

@router.get("/predictive")
def predictive():
    return ai_service.get_predictive_insights()