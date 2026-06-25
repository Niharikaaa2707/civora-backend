from fastapi import APIRouter
from app.services.db import read_all
from app.services.ai_service import get_predictive_insights
from collections import Counter
from datetime import datetime

router = APIRouter()

@router.get("/summary")
def summary():
    issues = read_all("issues")
    total    = len(issues)
    open_    = len([i for i in issues if i.get("status") not in ("RESOLVED","REJECTED")])
    resolved = len([i for i in issues if i.get("status") == "RESOLVED"])
    critical = len([i for i in issues if i.get("severity") == "CRITICAL"])
    today    = datetime.utcnow().date().isoformat()
    resolved_today = len([i for i in issues if (i.get("resolved_at") or "").startswith(today)])
    return {
        "total": total, "open": open_, "resolved": resolved,
        "critical": critical, "resolved_today": resolved_today,
        "resolution_rate": round(resolved / max(total, 1) * 100, 1),
    }

@router.get("/by-category")
def by_category():
    issues = read_all("issues")
    counts = Counter(i.get("category","Other") for i in issues)
    return [{"category": k, "count": v} for k, v in counts.most_common(10)]

@router.get("/by-severity")
def by_severity():
    issues = read_all("issues")
    counts = Counter(i.get("severity","MEDIUM") for i in issues)
    return dict(counts)

@router.get("/by-status")
def by_status():
    issues = read_all("issues")
    counts = Counter(i.get("status","PENDING_REVIEW") for i in issues)
    return dict(counts)

@router.get("/resolution-time")
def resolution_time():
    issues = read_all("issues")
    resolved = [i for i in issues if i.get("resolved_at") and i.get("created_at")]
    if not resolved:
        return {"avg_days": 0, "data": []}
    data = []
    for i in resolved:
        try:
            c = datetime.fromisoformat(i["created_at"])
            r = datetime.fromisoformat(i["resolved_at"])
            days = round((r - c).total_seconds() / 86400, 1)
            data.append({"category": i.get("category","Other"), "days": days})
        except Exception:
            pass
    avg = round(sum(d["days"] for d in data) / max(len(data), 1), 1)
    return {"avg_days": avg, "data": data}

@router.get("/leaderboard")
def leaderboard():
    from app.services.gamification_service import get_leaderboard
    return get_leaderboard()

@router.get("/predictive")
def predictive():
    return get_predictive_insights()