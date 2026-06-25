import os, json, math
from typing import Optional
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import io
from app.services.db import read_all

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    _model = genai.GenerativeModel("gemini-2.5-flash")
else:
    _model = None

ISSUE_CATEGORIES = [
    "Pothole / Road Damage", "Broken Streetlight", "Garbage / Waste",
    "Water Leakage / Waterlogging", "Sewage / Blocked Drain",
    "Damaged Footpath", "Illegal Dumping", "Broken Traffic Signal",
    "Damaged Public Property", "Open Manhole", "Electrical Wire Hazard", "Other"
]

DEPARTMENTS = {
    "Pothole / Road Damage":        "Roads & Infrastructure Dept",
    "Broken Streetlight":           "Electrical / Smart City Dept",
    "Garbage / Waste":              "Sanitation & Waste Management",
    "Water Leakage / Waterlogging": "Water & Sewerage Board",
    "Sewage / Blocked Drain":       "Water & Sewerage Board",
    "Damaged Footpath":             "Roads & Infrastructure Dept",
    "Illegal Dumping":              "Sanitation & Waste Management",
    "Broken Traffic Signal":        "Traffic & Transport Dept",
    "Damaged Public Property":      "Municipal Corporation",
    "Open Manhole":                 "Water & Sewerage Board",
    "Electrical Wire Hazard":       "Electrical / Smart City Dept",
    "Other":                        "Municipal Corporation",
}

SLA_DAYS = {"CRITICAL": 1, "HIGH": 3, "MEDIUM": 7, "LOW": 14}

def analyze_image(image_bytes: bytes, description: str = "") -> dict:
    if not _model:
        return _fallback_analysis(description)
    try:
        image = Image.open(io.BytesIO(image_bytes))
        prompt = f"""
You are a civic infrastructure expert AI. Analyse this image.
Additional description: "{description}"
Return ONLY valid JSON with these keys:
{{
  "detected_category": "<category>",
  "confidence": <float 0.0-1.0>,
  "severity": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "severity_reason": "<1 sentence>",
  "risk_description": "<1-2 sentences>",
  "department": "<department>",
  "resolution_plan": ["<step1>","<step2>","<step3>","<step4>"],
  "priority_score": <1-10>,
  "estimated_days": <integer>,
  "immediate_action": "<single step>",
  "ai_labels": ["<label1>","<label2>"]
}}
Categories: {', '.join(ISSUE_CATEGORIES)}
"""
        response = _model.generate_content([prompt, image])
        raw = response.text.strip().replace("```json","").replace("```","").strip()
        result = json.loads(raw)
        cat = result.get("detected_category", "Other")
        if not result.get("department"):
            result["department"] = DEPARTMENTS.get(cat, "Municipal Corporation")
        result["sla_days"] = SLA_DAYS.get(result.get("severity","MEDIUM"), 7)
        return result
    except Exception:
        return _fallback_analysis(description)

def analyze_text(description: str) -> dict:
    if not _model:
        return {"category": "Other", "urgency": "MEDIUM", "keywords": []}
    try:
        prompt = f"""
Analyse this civic issue description: "{description}"
Return ONLY valid JSON:
{{
  "detected_category": "<category>",
  "confidence": 0.7,
  "severity": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "severity_reason": "<1 sentence>",
  "risk_description": "<1-2 sentences>",
  "department": "<department>",
  "resolution_plan": ["<step1>","<step2>","<step3>"],
  "priority_score": <1-10>,
  "estimated_days": <integer>,
  "immediate_action": "<single step>",
  "ai_labels": ["<label1>","<label2>"],
  "sla_days": <integer>
}}
Categories: {', '.join(ISSUE_CATEGORIES)}
"""
        response = _model.generate_content(prompt)
        raw = response.text.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception:
        return _fallback_analysis(description)

def get_resolution_plan(issue: dict) -> dict:
    if not _model:
        return {"action_plan": ["Inspect site","Deploy team","Fix issue","Document"], "sla_benchmark": "7 days"}
    try:
        prompt = f"""
You are a civic admin AI. Generate resolution plan for:
Category: {issue.get('category')}
Severity: {issue.get('severity')}
Location: {issue.get('location')}
Description: {issue.get('description')}

Return ONLY valid JSON:
{{
  "action_plan": ["<step1>","<step2>","<step3>","<step4>","<step5>"],
  "resources": ["<resource1>","<resource2>"],
  "sla_benchmark": "<e.g. 24 hours>",
  "official_notice": "<2 sentence notice>",
  "success_criteria": "<how to confirm resolved>"
}}
"""
        response = _model.generate_content(prompt)
        raw = response.text.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception:
        return {"action_plan": ["Inspect","Deploy team","Fix","Document"], "sla_benchmark": "7 days", "official_notice": "Team assigned.", "resources": ["Field team"], "success_criteria": "Photo evidence submitted"}

def detect_duplicate(new_issue: dict, radius_m: float = 200) -> Optional[str]:
    existing = read_all("issues")
    new_lat = float(new_issue.get("lat") or 0)
    new_lon = float(new_issue.get("lon") or 0)
    new_cat = new_issue.get("category", "").lower()
    if not new_lat or not new_lon:
        return None
    for issue in existing:
        if issue.get("status") == "RESOLVED":
            continue
        try:
            lat = float(issue.get("lat") or 0)
            lon = float(issue.get("lon") or 0)
        except Exception:
            continue
        if not lat or not lon:
            continue
        dist = _haversine(new_lat, new_lon, lat, lon)
        if dist < radius_m and new_cat in issue.get("category","").lower():
            return issue["id"]
    return None

def get_predictive_insights() -> dict:
    issues = read_all("issues")
    if len(issues) < 3:
        return {"message": "Not enough data yet.", "trends": [], "alerts": []}
    cat_counts: dict = {}
    cat_open: dict = {}
    for issue in issues:
        cat = issue.get("category", "Other")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if issue.get("status") not in ("RESOLVED","REJECTED"):
            cat_open[cat] = cat_open.get(cat, 0) + 1
    total = len(issues)
    trends = []
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        trends.append({
            "category": cat, "count": count,
            "percentage": round(count/total*100, 1),
            "open": cat_open.get(cat, 0),
            "department": DEPARTMENTS.get(cat, "Municipal Corporation"),
        })
    alerts = []
    if trends and trends[0]["count"] >= 3:
        alerts.append({"type":"surge","message":f"⚠️ {trends[0]['category']} issues spiking ({trends[0]['count']} reports).","severity":"HIGH"})
    high_open = [t for t in trends if t["open"] >= 5]
    for h in high_open[:2]:
        alerts.append({"type":"backlog","message":f"📌 {h['open']} unresolved {h['category']} issues.","severity":"MEDIUM"})
    resolved = [i for i in issues if i.get("resolved_at") and i.get("created_at")]
    avg_days = 0.0
    if resolved:
        deltas = []
        for i in resolved:
            try:
                c = datetime.fromisoformat(i["created_at"])
                r = datetime.fromisoformat(i["resolved_at"])
                deltas.append((r-c).total_seconds()/86400)
            except Exception:
                pass
        if deltas:
            avg_days = round(sum(deltas)/len(deltas), 1)
    return {
        "total_issues": total, "trends": trends, "alerts": alerts,
        "avg_resolution": avg_days,
        "resolution_rate": round(len([i for i in issues if i.get("status")=="RESOLVED"])/max(total,1)*100, 1),
    }

def _fallback_analysis(description: str) -> dict:
    return {
        "detected_category": "Other", "confidence": 0.5,
        "severity": "MEDIUM", "severity_reason": "Auto-classified",
        "risk_description": "Potential public inconvenience.",
        "department": "Municipal Corporation",
        "resolution_plan": ["Inspect site","Deploy team","Complete repair","Document"],
        "priority_score": 5, "estimated_days": 7,
        "immediate_action": "Flag for inspection",
        "ai_labels": ["civic_issue"], "sla_days": 7,
    }

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dlam = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))