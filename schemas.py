"""
Pydantic Schemas for request/response validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================
# Page ID Schemas
# ============================================

class PageIDCreate(BaseModel):
    page_id: str = Field(..., min_length=5, max_length=100, description="Facebook Page ID e.g. fb201283739733566")
    name: str = Field(..., min_length=1, max_length=100, description="Short name e.g. ro54_s")
    user: str = Field(..., min_length=1, max_length=100, description="Assigned user")
    tl: str = Field(..., min_length=1, max_length=100, description="Team lead")
    account_name: str = Field(..., min_length=1, max_length=200, description="Account name")
    is_active: bool = True


class PageIDUpdate(BaseModel):
    page_id: Optional[str] = Field(None, min_length=5, max_length=100)
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    user: Optional[str] = Field(None, min_length=1, max_length=100)
    tl: Optional[str] = Field(None, min_length=1, max_length=100)
    account_name: Optional[str] = Field(None, min_length=1, max_length=200)
    is_active: Optional[bool] = None


class PageIDResponse(BaseModel):
    id: int
    page_id: str
    name: str
    user: str
    tl: str
    account_name: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PageIDListResponse(BaseModel):
    items: List[PageIDResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# ============================================
# ManyChat Format (for automation consumption)
# ============================================

class ManyChatPageFormat(BaseModel):
    """Format matching page_ids.json structure"""
    id: str
    name: str
    user: str
    tl: str
    account_name: str


class ManyChatPagesResponse(BaseModel):
    """Full page_ids.json compatible response"""
    pages: List[ManyChatPageFormat]
    config: dict = {
        "extract_all_active": True,
        "output_separate_files": False,
        "output_combined_file": True,
    }
    total: int


# ============================================
# Auth Schemas
# ============================================

class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# ============================================
# Generic Responses
# ============================================

class MessageResponse(BaseModel):
    message: str
    success: bool = True


class ErrorResponse(BaseModel):
    detail: str
    success: bool = False
