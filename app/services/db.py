import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")

COLLECTIONS = ["users", "issues", "validations", "status_history",
               "gamification_log", "notifications", "missions", "media_assets"]

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    for col in COLLECTIONS:
        path = _path(col)
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump([], f)
    _seed_missions()

def _path(collection: str) -> str:
    return os.path.join(DATA_DIR, f"{collection}.json")

def read_all(collection: str) -> List[Dict]:
    try:
        with open(_path(collection)) as f:
            return json.load(f)
    except Exception:
        return []

def write_all(collection: str, data: List[Dict]):
    with open(_path(collection), "w") as f:
        json.dump(data, f, indent=2, default=str)

def find_one(collection: str, **kwargs) -> Optional[Dict]:
    for item in read_all(collection):
        if all(item.get(k) == v for k, v in kwargs.items()):
            return item
    return None

def find_many(collection: str, **kwargs) -> List[Dict]:
    return [
        item for item in read_all(collection)
        if all(item.get(k) == v for k, v in kwargs.items())
    ]

def insert_one(collection: str, doc: Dict) -> Dict:
    if "id" not in doc:
        doc["id"] = str(uuid.uuid4())
    if "created_at" not in doc:
        doc["created_at"] = datetime.utcnow().isoformat()
    data = read_all(collection)
    data.append(doc)
    write_all(collection, data)
    return doc

def update_one(collection: str, doc_id: str, updates: Dict) -> Optional[Dict]:
    data = read_all(collection)
    for i, item in enumerate(data):
        if item.get("id") == doc_id:
            data[i].update(updates)
            data[i]["updated_at"] = datetime.utcnow().isoformat()
            write_all(collection, data)
            return data[i]
    return None

def delete_one(collection: str, doc_id: str) -> bool:
    data = read_all(collection)
    new_data = [item for item in data if item.get("id") != doc_id]
    if len(new_data) < len(data):
        write_all(collection, new_data)
        return True
    return False

def generate_issue_id() -> str:
    issues = read_all("issues")
    return f"CIV-{len(issues)+1:04d}"

def _seed_missions():
    if not read_all("missions"):
        missions = [
            {"id": "m1", "title": "Pothole Hunter",    "description": "Report 3 road issues this week",          "target_action": "report",   "category": "Pothole",    "target_count": 3,  "xp_reward": 100, "badge_icon": "🛣️",  "active": True},
            {"id": "m2", "title": "Light Up the City", "description": "Report 5 broken streetlights in your area","target_action": "report",   "category": "Streetlight","target_count": 5,  "xp_reward": 150, "badge_icon": "💡",  "active": True},
            {"id": "m3", "title": "Clean Sweep",        "description": "Validate 10 waste management issues",     "target_action": "validate", "category": "Garbage",    "target_count": 10, "xp_reward": 80,  "badge_icon": "🧹",  "active": True},
            {"id": "m4", "title": "Water Watch",        "description": "Report 2 water leakage issues",           "target_action": "report",   "category": "Water",      "target_count": 2,  "xp_reward": 120, "badge_icon": "💧",  "active": True},
            {"id": "m5", "title": "First Responder",    "description": "Be first to report a CRITICAL issue",     "target_action": "critical", "category": "Any",        "target_count": 1,  "xp_reward": 200, "badge_icon": "🚨",  "active": True},
        ]
        write_all("missions", missions)