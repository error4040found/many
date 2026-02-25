"""
SQLAlchemy Models for ManyChat Dashboard
- PageID: stores page configuration data
- User: stores dashboard users for authentication
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, func
from database import Base
from datetime import datetime


class PageID(Base):
    """Page IDs table - stores ManyChat page configurations"""
    __tablename__ = "page_ids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(String(100), unique=True, nullable=False, index=True, comment="Facebook Page ID e.g. fb201283739733566")
    name = Column(String(100), nullable=False, comment="Short name e.g. ro54_s")
    user = Column(String(100), nullable=False, index=True, comment="Assigned user e.g. Aarti")
    tl = Column(String(100), nullable=False, index=True, comment="Team lead e.g. Sumant sir")
    account_name = Column(String(200), nullable=False, comment="Account name e.g. BHUella")
    is_active = Column(Boolean, default=True, nullable=False, comment="Whether this page is active")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "page_id": self.page_id,
            "name": self.name,
            "user": self.user,
            "tl": self.tl,
            "account_name": self.account_name,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_page_ids_format(self):
        """Convert to the format used by page_ids.json"""
        return {
            "id": self.page_id,
            "name": self.name,
            "user": self.user,
            "tl": self.tl,
            "account_name": self.account_name,
        }


class DashboardUser(Base):
    """Dashboard users for authentication"""
    __tablename__ = "dashboard_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), default="viewer", nullable=False, comment="admin, editor, viewer")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    last_login = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
