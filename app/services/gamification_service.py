from app.services.db import find_one, update_one, insert_one, read_all, find_many

XP_TABLE = {
    "submit_issue": 10, "photo_evidence": 5, "critical_report": 15,
    "validate_issue": 3, "issue_resolved": 20, "daily_streak_7": 25,
    "complete_mission": 50, "top_reporter": 100, "refer_citizen": 15,
}

TIERS = [
    (0, "Newcomer", "🌱"), (100, "Scout", "🔭"),
    (500, "Watchdog", "🐕"), (1500, "Crusader", "⚔️"), (4000, "Hero", "🏆"),
]

ACHIEVEMENT_BADGES = {
    "first_report":    {"name": "First Report",       "icon": "📋", "desc": "Filed your first civic issue"},
    "photo_10":        {"name": "Photo Evidence",     "icon": "📸", "desc": "Uploaded 10+ photo reports"},
    "streak_7":        {"name": "Streak Warrior",     "icon": "🔥", "desc": "7-day login streak"},
    "critical_finder": {"name": "Critical Finder",    "icon": "🚨", "desc": "Reported 5 CRITICAL issues"},
    "community_star":  {"name": "Community Star",     "icon": "⭐", "desc": "Received 50+ upvotes on reports"},
    "ward_champion":   {"name": "Ward Champion",      "icon": "👑", "desc": "Top reporter in your ward"},
    "speed_resolver":  {"name": "Speed Resolver",     "icon": "⚡", "desc": "All reports resolved within 48h"},
    "night_watcher":   {"name": "Night Watcher",      "icon": "🌙", "desc": "Reported 5 issues after 10 PM"},
    "validator_50":    {"name": "Verified Validator", "icon": "✅", "desc": "Upvoted 50 confirmed issues"},
}

def get_tier(xp: int) -> dict:
    tier_name, tier_icon = TIERS[0][1], TIERS[0][2]
    for min_xp, name, icon in TIERS:
        if xp >= min_xp:
            tier_name, tier_icon = name, icon
    return {"name": tier_name, "icon": tier_icon}

def award_xp(user_id: str, action: str, issue_id: str = None) -> dict:
    xp = XP_TABLE.get(action, 0)
    if xp == 0:
        return {}
    user = find_one("users", id=user_id)
    if not user:
        return {}
    new_xp  = user.get("xp_points", 0) + xp
    new_tier = get_tier(new_xp)
    update_one("users", user_id, {"xp_points": new_xp, "tier": new_tier["name"]})
    insert_one("gamification_log", {
        "user_id": user_id, "action": action,
        "xp_awarded": xp, "issue_id": issue_id,
    })
    _check_badges(user_id)
    return {"xp_awarded": xp, "total_xp": new_xp, "tier": new_tier}

def _check_badges(user_id: str):
    user = find_one("users", id=user_id)
    if not user:
        return
    badges = set(user.get("badges", []))
    issues = find_many("issues", reporter_id=user_id)
    if len(issues) >= 1:  badges.add("first_report")
    if len(issues) >= 10: badges.add("photo_10")
    critical = [i for i in issues if i.get("severity") == "CRITICAL"]
    if len(critical) >= 5: badges.add("critical_finder")
    new_badges = list(badges)
    if new_badges != user.get("badges", []):
        update_one("users", user_id, {"badges": new_badges})

def get_leaderboard(limit: int = 10) -> list:
    users = read_all("users")
    board = []
    for u in users:
        if u.get("role") == "citizen":
            board.append({
                "name":   u["name"],
                "xp":     u.get("xp_points", 0),
                "tier":   u.get("tier", "Newcomer"),
                "badges": len(u.get("badges", [])),
                "issues": len(find_many("issues", reporter_id=u["id"])),
            })
    board.sort(key=lambda x: x["xp"], reverse=True)
    return board[:limit]

def get_user_stats(user_id: str) -> dict:
    user = find_one("users", id=user_id)
    if not user:
        return {}
    issues    = find_many("issues", reporter_id=user_id)
    resolved  = [i for i in issues if i.get("status") == "RESOLVED"]
    critical  = [i for i in issues if i.get("severity") == "CRITICAL"]
    xp        = user.get("xp_points", 0)
    tier_info = get_tier(xp)
    next_tier = _next_tier(xp)
    badges_detail = []
    for badge_id in user.get("badges", []):
        if badge_id in ACHIEVEMENT_BADGES:
            badges_detail.append({"id": badge_id, **ACHIEVEMENT_BADGES[badge_id]})
    return {
        "xp": xp, "tier": tier_info, "next_tier": next_tier,
        "total_reports": len(issues), "resolved": len(resolved),
        "critical_found": len(critical), "badges": badges_detail,
        "all_badges": ACHIEVEMENT_BADGES,
    }

def _next_tier(xp: int) -> dict:
    for min_xp, name, icon in TIERS:
        if xp < min_xp:
            return {"name": name, "icon": icon, "xp_needed": min_xp - xp, "min_xp": min_xp}
    return {"name": "Max Tier", "icon": "🏆", "xp_needed": 0, "min_xp": xp}