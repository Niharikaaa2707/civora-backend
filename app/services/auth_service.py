import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional
from app.services.db import find_one, insert_one

SECRET_KEY = os.environ.get("JWT_SECRET", "community-hero-secret-change-in-prod")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_access_token(data: dict, expires_delta=None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None

def register_user(name: str, email: str, password: str, phone: str = "") -> dict:
    if find_one("users", email=email):
        raise ValueError("Email already registered")
    user = insert_one("users", {
        "name":      name,
        "email":     email,
        "phone":     phone,
        "password":  hash_password(password),
        "xp_points": 0,
        "tier":      "Newcomer",
        "badges":    [],
        "ward":      "",
        "role":      "citizen",
    })
    user.pop("password", None)
    return user

def login_user(email: str, password: str) -> dict:
    user = find_one("users", email=email)
    if not user or not verify_password(password, user["password"]):
        raise ValueError("Invalid credentials")
    token = create_access_token({"sub": user["id"], "email": user["email"], "role": user["role"]})
    safe_user = {k: v for k, v in user.items() if k != "password"}
    return {"access_token": token, "token_type": "bearer", "user": safe_user}

def get_current_user(token: str) -> Optional[dict]:
    payload = decode_token(token)
    if not payload:
        return None
    return find_one("users", id=payload.get("sub"))