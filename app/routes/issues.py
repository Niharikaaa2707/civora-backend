from fastapi import APIRouter, HTTPException, Header, UploadFile, File, Form
from typing import Optional
from datetime import datetime
from app.services import auth_service, ai_service, gamification_service
from app.services.db import (
    read_all, find_one, insert_one, update_one, delete_one,
    find_many, generate_issue_id
)
import base64

router = APIRouter()

def _get_user(auth_header):
    if not auth_header or " " not in auth_header:
        return None
    return auth_service.get_current_user(auth_header.split(" ", 1)[1])

@router.post("")
async def submit_issue(
    description: str = Form(...),
    location:    str = Form(...),
    lat:         str = Form(""),
    lon:         str = Form(""),
    ward:        str = Form(""),
    image: Optional[UploadFile] = File(None),
    authorization: Optional[str] = Header(None),
):
    user = _get_user(authorization)
    if not user:
        raise HTTPException(401, "Auth required")

    image_b64 = ""
    ai_result = {}

    if image and image.filename:
        img_bytes = await image.read()
        image_b64 = base64.b64encode(img_bytes).decode()
        ai_result = ai_service.analyze_image(img_bytes, description)
    else:
        ai_result = ai_service.analyze_text(description)

    issue_id = generate_issue_id()
    issue = insert_one("issues", {
        "id":            issue_id,
        "title":         ai_result.get("detected_category", "Civic Issue"),
        "description":   description,
        "category":      ai_result.get("detected_category", "Other"),
        "severity":      ai_result.get("severity", "MEDIUM"),
        "status":        "PENDING_REVIEW",
        "location":      location,
        "lat":           lat,
        "lon":           lon,
        "ward":          ward,
        "reporter_id":   user["id"],
        "reporter_name": user["name"],
        "department":    ai_result.get("department", "Municipal Corporation"),
        "ai_analysis":   ai_result,
        "ai_confidence": ai_result.get("confidence", 0.5),
        "priority_score":ai_result.get("priority_score", 5),
        "upvotes":       0,
        "upvoted_by":    [],
        "image_b64":     image_b64,
        "duplicate_of":  None,
        "sla_days":      ai_result.get("sla_days", 7),
        "resolved_at":   None,
    })

    xp = gamification_service.award_xp(user["id"], "submit_issue", issue_id)
    if image_b64:
        gamification_service.award_xp(user["id"], "photo_evidence", issue_id)
    if ai_result.get("severity") == "CRITICAL":
        gamification_service.award_xp(user["id"], "critical_report", issue_id)

    return {"issue": issue, "xp": xp}

@router.get("")
def list_issues(
    sort:     str = "newest",
    status:   str = "",
    severity: str = "",
    limit:    int = 50,
):
    issues = read_all("issues")
    if status:
        issues = [i for i in issues if i.get("status") == status]
    if severity:
        issues = [i for i in issues if i.get("severity") == severity]
    if sort == "upvotes":
        issues.sort(key=lambda x: x.get("upvotes", 0), reverse=True)
    elif sort == "priority":
        issues.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    elif sort == "critical":
        order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        issues.sort(key=lambda x: order.get(x.get("severity", "LOW"), 4))
    else:
        issues.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"issues": issues[:limit], "total": len(issues)}

@router.get("/nearby")
def nearby(lat: float, lon: float, radius: float = 500):
    import math
    issues = read_all("issues")
    result = []
    for i in issues:
        try:
            ilat, ilon = float(i.get("lat", 0)), float(i.get("lon", 0))
            if not ilat or not ilon:
                continue
            R = 6371000
            phi1, phi2 = math.radians(lat), math.radians(ilat)
            dphi = math.radians(ilat - lat)
            dlam = math.radians(ilon - lon)
            a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
            dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            if dist <= radius:
                result.append({**i, "distance_m": round(dist)})
        except Exception:
            pass
    result.sort(key=lambda x: x["distance_m"])
    return {"issues": result}

@router.get("/heatmap")
def heatmap():
    issues = read_all("issues")
    features = []
    for i in issues:
        try:
            lat, lon = float(i.get("lat", 0)), float(i.get("lon", 0))
            if lat and lon:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"severity": i.get("severity"), "id": i.get("id")},
                })
        except Exception:
            pass
    return {"type": "FeatureCollection", "features": features}

@router.get("/{issue_id}")
def get_issue(issue_id: str):
    issue = find_one("issues", id=issue_id)
    if not issue:
        raise HTTPException(404, "Issue not found")
    return issue

@router.post("/{issue_id}/validate")
def validate_issue(
    issue_id: str,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    user = _get_user(authorization)
    if not user:
        raise HTTPException(401, "Auth required")
    issue = find_one("issues", id=issue_id)
    if not issue:
        raise HTTPException(404, "Issue not found")
    if user["id"] in issue.get("upvoted_by", []):
        raise HTTPException(400, "Already voted")
    upvoted_by = issue.get("upvoted_by", []) + [user["id"]]
    update_one("issues", issue_id, {
        "upvotes":    issue.get("upvotes", 0) + 1,
        "upvoted_by": upvoted_by,
    })
    xp = gamification_service.award_xp(user["id"], "validate_issue", issue_id)
    return {"message": "Vote recorded", "xp": xp}

@router.patch("/{issue_id}/status")
def update_status(
    issue_id: str,
    body: dict,
    authorization: Optional[str] = Header(None),
):
    user = _get_user(authorization)
    if not user:
        raise HTTPException(401, "Auth required")
    issue = find_one("issues", id=issue_id)
    if not issue:
        raise HTTPException(404, "Issue not found")
    new_status = body.get("status")
    updates = {"status": new_status}
    if new_status == "RESOLVED":
        updates["resolved_at"] = datetime.utcnow().isoformat()
        gamification_service.award_xp(issue["reporter_id"], "issue_resolved", issue_id)
    update_one("issues", issue_id, updates)
    return {"message": "Status updated"}

@router.delete("/{issue_id}")
def delete_issue(
    issue_id: str,
    authorization: Optional[str] = Header(None),
):
    user = _get_user(authorization)
    if not user:
        raise HTTPException(401, "Auth required")
    issue = find_one("issues", id=issue_id)
    if not issue:
        raise HTTPException(404, "Issue not found")
    if issue["reporter_id"] != user["id"] and user.get("role") != "admin":
        raise HTTPException(403, "Not allowed")
    delete_one("issues", issue_id)
    return {"message": "Deleted"}