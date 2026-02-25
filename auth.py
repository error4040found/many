"""
Authentication utilities - password hashing, session management
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy.orm import Session
from models import DashboardUser

# Simple in-memory session store (for production, use Redis or database sessions)
_sessions: Dict[str, dict] = {}

# Session expiry: 24 hours
SESSION_EXPIRY_HOURS = 24


def hash_password(password: str) -> str:
    """Hash password with SHA-256 + salt"""
    salt = "manychat_dashboard_2026"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return hash_password(plain_password) == hashed_password


def authenticate_user(db: Session, username: str, password: str) -> Optional[DashboardUser]:
    """Authenticate user and return user object or None"""
    user = db.query(DashboardUser).filter(
        DashboardUser.username == username,
        DashboardUser.is_active == True
    ).first()

    if user and verify_password(password, user.password_hash):
        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        return user
    return None


def create_session(user: DashboardUser) -> str:
    """Create a session token for authenticated user"""
    token = secrets.token_hex(32)
    _sessions[token] = {
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS),
    }
    return token


def get_session(token: str) -> Optional[dict]:
    """Get session data from token, returns None if expired or invalid"""
    if not token or token not in _sessions:
        return None
    
    session = _sessions[token]
    if datetime.utcnow() > session["expires_at"]:
        # Session expired, clean up
        del _sessions[token]
        return None
    
    return session


def destroy_session(token: str):
    """Remove a session"""
    if token in _sessions:
        del _sessions[token]


def create_default_users(db: Session):
    """Create 3 default users if they don't exist"""
    default_users = [
        {
            "username": "admin",
            "password": "admin@123",
            "full_name": "Administrator",
            "role": "admin",
        },
        {
            "username": "babu",
            "password": "babu@123",
            "full_name": "Veera Babu",
            "role": "editor",
        },
        {
            "username": "subhajit",
            "password": "subhajit@123",
            "full_name": "Subhajit",
            "role": "editor",
        },
    ]

    created_count = 0
    for user_data in default_users:
        existing = db.query(DashboardUser).filter(
            DashboardUser.username == user_data["username"]
        ).first()

        if not existing:
            new_user = DashboardUser(
                username=user_data["username"],
                password_hash=hash_password(user_data["password"]),
                full_name=user_data["full_name"],
                role=user_data["role"],
                is_active=True,
            )
            db.add(new_user)
            created_count += 1

    if created_count > 0:
        db.commit()
        print(f"✅ Created {created_count} default dashboard users")
    else:
        print("ℹ️  Default dashboard users already exist")
