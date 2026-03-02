"""
ManyChat Dashboard - FastAPI Application
=========================================
Full-featured dashboard with:
- Page IDs CRUD management with pagination
- Session-based authentication (3 users)
- REST API for ManyChat automation consumption
- Google Sheets fallback data fetching
- Email alerts on failure
- Jinja2 HTML templates (no separate frontend server)

Run: uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
import io
import csv
import json
import math
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import (
    FastAPI,
    Request,
    Response,
    Depends,
    HTTPException,
    Form,
    Query,
    UploadFile,
    File,
)
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from database import get_db, init_db, SessionLocal
from models import PageID, DashboardUser
from schemas import (
    PageIDCreate,
    PageIDUpdate,
    PageIDResponse,
    PageIDListResponse,
    ManyChatPageFormat,
    ManyChatPagesResponse,
    MessageResponse,
    LoginRequest,
    UserResponse,
)
from auth import (
    authenticate_user,
    create_session,
    get_session,
    destroy_session,
    create_default_users,
    hash_password,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manychat_dashboard")


def normalize_name(value: str) -> str:
    """Normalize a name to title case for consistent storage.
    e.g. 'subhajit sir' and 'Subhajit sir' both become 'Subhajit Sir'
    """
    if not value or not value.strip():
        return value
    return value.strip().title()


# ============================================
# App Initialization
# ============================================
app = FastAPI(
    title="ManyChat Page IDs Dashboard",
    description="Dashboard to manage ManyChat page IDs with API for automation",
    version="1.0.0",
)

# Templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ============================================
# Startup Event
# ============================================
@app.on_event("startup")
def startup_event():
    """Initialize database and create default users on startup"""
    logger.info("🚀 Starting ManyChat Dashboard...")
    init_db()
    db = SessionLocal()
    try:
        create_default_users(db)
        # Normalize existing user/tl names to title case for consistency
        _normalize_existing_data(db)
    finally:
        db.close()
    logger.info("✅ Dashboard ready!")


def _normalize_existing_data(db: Session):
    """Normalize user and tl fields in existing records to title case."""
    pages = db.query(PageID).all()
    updated = 0
    for p in pages:
        new_user = normalize_name(p.user) if p.user else p.user
        new_tl = normalize_name(p.tl) if p.tl else p.tl
        new_account = (
            normalize_name(p.account_name) if p.account_name else p.account_name
        )
        if new_user != p.user or new_tl != p.tl or new_account != p.account_name:
            p.user = new_user
            p.tl = new_tl
            p.account_name = new_account
            updated += 1
    if updated:
        db.commit()
        logger.info(f"✅ Normalized {updated} records (user/tl/account name casing)")


# ============================================
# Auth Dependency for Dashboard (cookie-based)
# ============================================
def get_current_user(request: Request) -> Optional[dict]:
    """Get current user from session cookie"""
    token = request.cookies.get("session_token")
    if not token:
        return None
    return get_session(token)


def require_auth(request: Request) -> dict:
    """Require authentication - redirect to login if not authenticated"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_editor(request: Request) -> dict:
    """Require editor or admin role"""
    user = require_auth(request)
    if user["role"] not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user


# ============================================
# AUTH ROUTES (Dashboard)
# ============================================


@app.get("/login", response_class=HTMLResponse, tags=["Auth"])
async def login_page(request: Request):
    """Show login page"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse, tags=["Auth"])
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Process login form"""
    user = authenticate_user(db, username, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"},
        )

    token = create_session(user)
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax",
    )
    return response


@app.get("/logout", tags=["Auth"])
async def logout(request: Request):
    """Logout and clear session"""
    token = request.cookies.get("session_token")
    if token:
        destroy_session(token)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_token")
    return response


# ============================================
# DASHBOARD ROUTES (HTML pages)
# ============================================


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Redirect to dashboard or login"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard_page(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=5, le=100),
    search: str = Query("", description="Search term"),
    user_filter: str = Query("", description="Filter by user"),
    tl_filter: str = Query("", description="Filter by team lead"),
    db: Session = Depends(get_db),
):
    """Main dashboard page with paginated page IDs"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)

    # Build query
    query = db.query(PageID)

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                PageID.page_id.ilike(search_term),
                PageID.name.ilike(search_term),
                PageID.user.ilike(search_term),
                PageID.tl.ilike(search_term),
                PageID.account_name.ilike(search_term),
            )
        )

    # Apply user filter (case-insensitive)
    if user_filter:
        query = query.filter(func.lower(PageID.user) == user_filter.lower())

    # Apply TL filter (case-insensitive)
    if tl_filter:
        query = query.filter(func.lower(PageID.tl) == tl_filter.lower())

    # Get total count
    total = query.count()
    total_pages = math.ceil(total / per_page) if total > 0 else 1

    # Ensure page is within bounds
    if page > total_pages:
        page = total_pages

    # Get paginated results
    offset = (page - 1) * per_page
    items = query.order_by(PageID.id.asc()).offset(offset).limit(per_page).all()

    # Get unique users and TLs for filter dropdowns (case-insensitive distinct)
    all_users_raw = db.query(PageID.user).distinct().order_by(PageID.user).all()
    all_tls_raw = db.query(PageID.tl).distinct().order_by(PageID.tl).all()
    # Deduplicate by lowercase to merge case variants
    all_users = sorted({normalize_name(u[0]) for u in all_users_raw if u[0]})
    all_tls = sorted({normalize_name(t[0]) for t in all_tls_raw if t[0]})

    # Stats
    total_all = db.query(PageID).count()
    active_count = db.query(PageID).filter(PageID.is_active == True).count()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user,
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "search": search,
            "user_filter": user_filter,
            "tl_filter": tl_filter,
            "all_users": all_users,
            "all_tls": all_tls,
            "total_all": total_all,
            "active_count": active_count,
        },
    )


@app.get("/dashboard/add", response_class=HTMLResponse, tags=["Dashboard"])
async def add_page_form(request: Request, db: Session = Depends(get_db)):
    """Show add page form"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user["role"] not in ("admin", "editor"):
        return RedirectResponse(url="/dashboard", status_code=302)

    all_users_raw = db.query(PageID.user).distinct().order_by(PageID.user).all()
    all_tls_raw = db.query(PageID.tl).distinct().order_by(PageID.tl).all()

    return templates.TemplateResponse(
        "add_edit.html",
        {
            "request": request,
            "user": current_user,
            "mode": "add",
            "page_item": None,
            "all_users": sorted({normalize_name(u[0]) for u in all_users_raw if u[0]}),
            "all_tls": sorted({normalize_name(t[0]) for t in all_tls_raw if t[0]}),
            "error": None,
        },
    )


@app.post("/dashboard/add", response_class=HTMLResponse, tags=["Dashboard"])
async def add_page_submit(
    request: Request,
    page_id: str = Form(...),
    name: str = Form(...),
    user_name: str = Form(...),
    tl: str = Form(...),
    account_name: str = Form(...),
    is_active: bool = Form(True),
    db: Session = Depends(get_db),
):
    """Process add page form"""
    current_user = get_current_user(request)
    if not current_user or current_user["role"] not in ("admin", "editor"):
        return RedirectResponse(url="/login", status_code=302)

    # Check if page_id already exists
    existing = db.query(PageID).filter(PageID.page_id == page_id).first()
    if existing:
        all_users_raw = db.query(PageID.user).distinct().order_by(PageID.user).all()
        all_tls_raw = db.query(PageID.tl).distinct().order_by(PageID.tl).all()
        return templates.TemplateResponse(
            "add_edit.html",
            {
                "request": request,
                "user": current_user,
                "mode": "add",
                "page_item": None,
                "all_users": sorted(
                    {normalize_name(u[0]) for u in all_users_raw if u[0]}
                ),
                "all_tls": sorted({normalize_name(t[0]) for t in all_tls_raw if t[0]}),
                "error": f"Page ID '{page_id}' already exists!",
            },
        )

    new_page = PageID(
        page_id=page_id,
        name=name,
        user=normalize_name(user_name),
        tl=normalize_name(tl),
        account_name=normalize_name(account_name),
        is_active=is_active,
    )
    db.add(new_page)
    db.commit()
    logger.info(f"✅ Page added: {page_id} by {current_user['username']}")
    return RedirectResponse(url="/dashboard?msg=added", status_code=302)


@app.get("/dashboard/edit/{item_id}", response_class=HTMLResponse, tags=["Dashboard"])
async def edit_page_form(request: Request, item_id: int, db: Session = Depends(get_db)):
    """Show edit page form"""
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user["role"] not in ("admin", "editor"):
        return RedirectResponse(url="/dashboard", status_code=302)

    page_item = db.query(PageID).filter(PageID.id == item_id).first()
    if not page_item:
        return RedirectResponse(url="/dashboard?msg=not_found", status_code=302)

    all_users_raw = db.query(PageID.user).distinct().order_by(PageID.user).all()
    all_tls_raw = db.query(PageID.tl).distinct().order_by(PageID.tl).all()

    return templates.TemplateResponse(
        "add_edit.html",
        {
            "request": request,
            "user": current_user,
            "mode": "edit",
            "page_item": page_item,
            "all_users": sorted({normalize_name(u[0]) for u in all_users_raw if u[0]}),
            "all_tls": sorted({normalize_name(t[0]) for t in all_tls_raw if t[0]}),
            "error": None,
        },
    )


@app.post("/dashboard/edit/{item_id}", response_class=HTMLResponse, tags=["Dashboard"])
async def edit_page_submit(
    request: Request,
    item_id: int,
    page_id: str = Form(...),
    name: str = Form(...),
    user_name: str = Form(...),
    tl: str = Form(...),
    account_name: str = Form(...),
    is_active: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Process edit page form"""
    current_user = get_current_user(request)
    if not current_user or current_user["role"] not in ("admin", "editor"):
        return RedirectResponse(url="/login", status_code=302)

    page_item = db.query(PageID).filter(PageID.id == item_id).first()
    if not page_item:
        return RedirectResponse(url="/dashboard?msg=not_found", status_code=302)

    # Check duplicate page_id (if changed)
    if page_id != page_item.page_id:
        existing = db.query(PageID).filter(PageID.page_id == page_id).first()
        if existing:
            all_users_raw = db.query(PageID.user).distinct().order_by(PageID.user).all()
            all_tls_raw = db.query(PageID.tl).distinct().order_by(PageID.tl).all()
            return templates.TemplateResponse(
                "add_edit.html",
                {
                    "request": request,
                    "user": current_user,
                    "mode": "edit",
                    "page_item": page_item,
                    "all_users": sorted(
                        {normalize_name(u[0]) for u in all_users_raw if u[0]}
                    ),
                    "all_tls": sorted(
                        {normalize_name(t[0]) for t in all_tls_raw if t[0]}
                    ),
                    "error": f"Page ID '{page_id}' already exists!",
                },
            )

    page_item.page_id = page_id
    page_item.name = name
    page_item.user = normalize_name(user_name)
    page_item.tl = normalize_name(tl)
    page_item.account_name = normalize_name(account_name)
    page_item.is_active = is_active
    db.commit()
    logger.info(f"✅ Page updated: {page_id} by {current_user['username']}")
    return RedirectResponse(url="/dashboard?msg=updated", status_code=302)


@app.post("/dashboard/delete/{item_id}", tags=["Dashboard"])
async def delete_page(request: Request, item_id: int, db: Session = Depends(get_db)):
    """Delete a page"""
    current_user = get_current_user(request)
    if not current_user or current_user["role"] not in ("admin", "editor"):
        return JSONResponse({"success": False, "detail": "Forbidden"}, status_code=403)

    page_item = db.query(PageID).filter(PageID.id == item_id).first()
    if not page_item:
        return JSONResponse({"success": False, "detail": "Not found"}, status_code=404)

    logger.info(f"🗑️ Page deleted: {page_item.page_id} by {current_user['username']}")
    db.delete(page_item)
    db.commit()
    return JSONResponse({"success": True, "message": "Page deleted successfully"})


@app.post("/dashboard/toggle/{item_id}", tags=["Dashboard"])
async def toggle_page_active(
    request: Request, item_id: int, db: Session = Depends(get_db)
):
    """Toggle a page's active status"""
    current_user = get_current_user(request)
    if not current_user or current_user["role"] not in ("admin", "editor"):
        return JSONResponse({"success": False, "detail": "Forbidden"}, status_code=403)

    page_item = db.query(PageID).filter(PageID.id == item_id).first()
    if not page_item:
        return JSONResponse({"success": False, "detail": "Not found"}, status_code=404)

    page_item.is_active = not page_item.is_active
    db.commit()
    status = "activated" if page_item.is_active else "deactivated"
    logger.info(f"🔄 Page {status}: {page_item.page_id} by {current_user['username']}")
    return JSONResponse(
        {"success": True, "is_active": page_item.is_active, "message": f"Page {status}"}
    )


# ============================================
# DELETE ALL
# ============================================


@app.post("/dashboard/delete-all", tags=["Dashboard"])
async def delete_all_pages(request: Request, db: Session = Depends(get_db)):
    """Delete ALL page IDs from the database (admin only)"""
    current_user = get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return JSONResponse(
            {"success": False, "detail": "Only admin can delete all pages"},
            status_code=403,
        )

    count = db.query(PageID).count()
    if count == 0:
        return JSONResponse(
            {"success": True, "deleted": 0, "message": "No pages to delete"}
        )

    db.query(PageID).delete()
    db.commit()
    logger.info(f"🗑️ ALL {count} pages deleted by {current_user['username']}")
    return JSONResponse(
        {
            "success": True,
            "deleted": count,
            "message": f"Successfully deleted all {count} page IDs",
        }
    )


# ============================================
# CSV UPLOAD
# ============================================


@app.post("/dashboard/upload-csv", tags=["Dashboard"])
async def upload_csv(
    request: Request, csv_file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """
    Upload a CSV file to bulk import page IDs.
    Expected CSV columns: page_id, name, user, tl, account_name
    - Columns can also be: id (instead of page_id)
    - First row must be the header row
    - Duplicate page_ids (already in DB) are skipped
    """
    current_user = get_current_user(request)
    if not current_user or current_user["role"] not in ("admin", "editor"):
        return JSONResponse({"success": False, "detail": "Forbidden"}, status_code=403)

    # Validate file type
    if not csv_file.filename:
        return JSONResponse(
            {"success": False, "detail": "No file provided"}, status_code=400
        )

    filename_lower = csv_file.filename.lower()
    if not filename_lower.endswith(".csv"):
        return JSONResponse(
            {"success": False, "detail": "Only .csv files are accepted"},
            status_code=400,
        )

    try:
        # Read file content
        content = await csv_file.read()

        # Try to decode with utf-8, fallback to latin-1
        try:
            text = content.decode("utf-8-sig")  # handles BOM
        except UnicodeDecodeError:
            text = content.decode("latin-1")

        if not text.strip():
            return JSONResponse(
                {"success": False, "detail": "CSV file is empty"}, status_code=400
            )

        # Parse CSV
        reader = csv.DictReader(io.StringIO(text))
        fields = reader.fieldnames

        if not fields:
            return JSONResponse(
                {"success": False, "detail": "CSV has no header row"}, status_code=400
            )

        # Normalize header names (lowercase, strip whitespace)
        field_map = {f.strip().lower(): f for f in fields}

        # Map possible column names to our required fields
        column_mapping = {
            "page_id": field_map.get("page_id")
            or field_map.get("id")
            or field_map.get("pageid")
            or field_map.get("page id"),
            "name": field_map.get("name")
            or field_map.get("page_name")
            or field_map.get("pagename"),
            "user": field_map.get("user")
            or field_map.get("username")
            or field_map.get("assigned_user"),
            "tl": field_map.get("tl")
            or field_map.get("team_lead")
            or field_map.get("teamlead")
            or field_map.get("team lead"),
            "account_name": field_map.get("account_name")
            or field_map.get("accountname")
            or field_map.get("account")
            or field_map.get("account name"),
        }

        # Check required columns exist
        missing = [k for k, v in column_mapping.items() if v is None]
        if missing:
            return JSONResponse(
                {
                    "success": False,
                    "detail": f"Missing required columns: {', '.join(missing)}. Found columns: {', '.join(fields)}. "
                    f"Expected: page_id (or id), name, user, tl, account_name",
                },
                status_code=400,
            )

        imported = 0
        skipped = 0
        errors = []
        row_num = 1  # header is row 0

        for row in reader:
            row_num += 1
            page_id_val = (row.get(column_mapping["page_id"]) or "").strip()
            name_val = (row.get(column_mapping["name"]) or "").strip()
            user_val = (row.get(column_mapping["user"]) or "").strip()
            tl_val = (row.get(column_mapping["tl"]) or "").strip()
            account_name_val = (row.get(column_mapping["account_name"]) or "").strip()

            # Skip empty rows
            if not page_id_val:
                errors.append(f"Row {row_num}: Missing page_id, skipped")
                continue

            if not name_val:
                errors.append(f"Row {row_num}: Missing name for {page_id_val}, skipped")
                continue

            # Check for duplicates in DB
            existing = db.query(PageID).filter(PageID.page_id == page_id_val).first()
            if existing:
                skipped += 1
                continue

            try:
                new_page = PageID(
                    page_id=page_id_val,
                    name=name_val,
                    user=normalize_name(user_val) or "Unassigned",
                    tl=normalize_name(tl_val) or "Unassigned",
                    account_name=normalize_name(account_name_val) or "Unknown",
                    is_active=True,
                )
                db.add(new_page)
                imported += 1
            except Exception as e:
                errors.append(f"Row {row_num} ({page_id_val}): {str(e)}")

        db.commit()
        logger.info(
            f"📤 CSV Upload by {current_user['username']}: {imported} imported, {skipped} skipped, {len(errors)} errors"
        )

        return JSONResponse(
            {
                "success": True,
                "imported": imported,
                "skipped": skipped,
                "errors": errors[:20],  # limit error messages
                "total_rows": row_num - 1,
                "message": f"Imported {imported} pages, skipped {skipped} duplicates"
                + (f", {len(errors)} errors" if errors else ""),
            }
        )

    except csv.Error as e:
        return JSONResponse(
            {"success": False, "detail": f"CSV parsing error: {str(e)}"},
            status_code=400,
        )
    except Exception as e:
        logger.error(f"CSV upload error: {str(e)}")
        return JSONResponse(
            {"success": False, "detail": f"Upload failed: {str(e)}"}, status_code=500
        )


# ============================================
# REST API ROUTES (for ManyChat automation)
# ============================================


@app.get("/api/page-ids", response_model=ManyChatPagesResponse, tags=["API"])
async def api_get_all_page_ids(
    active_only: bool = Query(True, description="Return only active pages"),
    db: Session = Depends(get_db),
):
    """
    GET all page IDs in ManyChat-compatible format.
    This is the main API endpoint consumed by the ManyChat automation.
    Returns data in the same format as page_ids.json.
    """
    query = db.query(PageID)
    if active_only:
        query = query.filter(PageID.is_active == True)

    pages = query.order_by(PageID.id.asc()).all()

    page_list = [
        ManyChatPageFormat(
            id=p.page_id,
            name=p.name,
            user=p.user,
            tl=p.tl,
            account_name=p.account_name,
        )
        for p in pages
    ]

    return ManyChatPagesResponse(
        pages=page_list,
        total=len(page_list),
        config={
            "extract_all_active": True,
            "output_separate_files": False,
            "output_combined_file": True,
        },
    )


@app.get("/api/page-ids/paginated", response_model=PageIDListResponse, tags=["API"])
async def api_get_page_ids_paginated(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query(""),
    user: str = Query(""),
    tl: str = Query(""),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
):
    """GET paginated page IDs with filtering"""
    query = db.query(PageID)

    if active_only:
        query = query.filter(PageID.is_active == True)

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                PageID.page_id.ilike(term),
                PageID.name.ilike(term),
                PageID.user.ilike(term),
                PageID.tl.ilike(term),
                PageID.account_name.ilike(term),
            )
        )

    if user:
        query = query.filter(PageID.user == user)
    if tl:
        query = query.filter(PageID.tl == tl)

    total = query.count()
    total_pages_count = math.ceil(total / per_page) if total > 0 else 1
    offset = (page - 1) * per_page
    items = query.order_by(PageID.id.asc()).offset(offset).limit(per_page).all()

    return PageIDListResponse(
        items=[PageIDResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages_count,
    )


@app.get("/api/page-ids/{item_id}", response_model=PageIDResponse, tags=["API"])
async def api_get_page_id(item_id: int, db: Session = Depends(get_db)):
    """GET single page ID by database ID"""
    page = db.query(PageID).filter(PageID.id == item_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page ID not found")
    return PageIDResponse.model_validate(page)


@app.post("/api/page-ids", response_model=PageIDResponse, tags=["API"])
async def api_create_page_id(data: PageIDCreate, db: Session = Depends(get_db)):
    """CREATE a new page ID"""
    existing = db.query(PageID).filter(PageID.page_id == data.page_id).first()
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Page ID '{data.page_id}' already exists"
        )

    new_page = PageID(
        page_id=data.page_id,
        name=data.name,
        user=data.user,
        tl=data.tl,
        account_name=data.account_name,
        is_active=data.is_active,
    )
    db.add(new_page)
    db.commit()
    db.refresh(new_page)
    return PageIDResponse.model_validate(new_page)


@app.put("/api/page-ids/{item_id}", response_model=PageIDResponse, tags=["API"])
async def api_update_page_id(
    item_id: int, data: PageIDUpdate, db: Session = Depends(get_db)
):
    """UPDATE a page ID"""
    page = db.query(PageID).filter(PageID.id == item_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page ID not found")

    update_data = data.model_dump(exclude_unset=True)
    if "page_id" in update_data and update_data["page_id"] != page.page_id:
        existing = (
            db.query(PageID).filter(PageID.page_id == update_data["page_id"]).first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Page ID '{update_data['page_id']}' already exists",
            )

    for key, value in update_data.items():
        setattr(page, key, value)

    db.commit()
    db.refresh(page)
    return PageIDResponse.model_validate(page)


@app.delete("/api/page-ids/{item_id}", response_model=MessageResponse, tags=["API"])
async def api_delete_page_id(item_id: int, db: Session = Depends(get_db)):
    """DELETE a page ID"""
    page = db.query(PageID).filter(PageID.id == item_id).first()
    if not page:
        raise HTTPException(status_code=404, detail="Page ID not found")

    db.delete(page)
    db.commit()
    return MessageResponse(message=f"Page ID '{page.page_id}' deleted successfully")


@app.get("/api/stats", tags=["API"])
async def api_get_stats(db: Session = Depends(get_db)):
    """GET dashboard statistics"""
    total = db.query(PageID).count()
    active = db.query(PageID).filter(PageID.is_active == True).count()
    inactive = total - active
    users = db.query(PageID.user).distinct().count()
    tls = db.query(PageID.tl).distinct().count()

    # User-wise counts
    user_counts = (
        db.query(PageID.user, func.count(PageID.id))
        .group_by(PageID.user)
        .order_by(func.count(PageID.id).desc())
        .all()
    )

    # TL-wise counts
    tl_counts = (
        db.query(PageID.tl, func.count(PageID.id))
        .group_by(PageID.tl)
        .order_by(func.count(PageID.id).desc())
        .all()
    )

    return {
        "total_pages": total,
        "active_pages": active,
        "inactive_pages": inactive,
        "total_users": users,
        "total_tls": tls,
        "user_counts": [{"user": u, "count": c} for u, c in user_counts],
        "tl_counts": [{"tl": t, "count": c} for t, c in tl_counts],
    }


@app.get("/api/health", tags=["API"])
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        count = db.query(PageID).count()
        return {
            "status": "healthy",
            "database": "connected",
            "page_ids_count": count,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)},
        )


# ============================================
# BULK OPERATIONS
# ============================================


@app.post("/api/page-ids/bulk-import", tags=["API"])
async def api_bulk_import(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Bulk import page IDs from JSON body.
    Expects: {"pages": [{"id": "fb...", "name": "...", "user": "...", "tl": "...", "account_name": "..."}]}
    """
    body = await request.json()
    pages = body.get("pages", [])

    if not pages:
        raise HTTPException(status_code=400, detail="No pages provided")

    imported = 0
    skipped = 0
    errors = []

    for page_data in pages:
        page_id = page_data.get("id", "")
        if not page_id:
            errors.append("Missing page ID")
            continue

        existing = db.query(PageID).filter(PageID.page_id == page_id).first()
        if existing:
            skipped += 1
            continue

        try:
            new_page = PageID(
                page_id=page_id,
                name=page_data.get("name", ""),
                user=normalize_name(page_data.get("user", "")),
                tl=normalize_name(page_data.get("tl", "")),
                account_name=normalize_name(page_data.get("account_name", "")),
                is_active=True,
            )
            db.add(new_page)
            imported += 1
        except Exception as e:
            errors.append(f"{page_id}: {str(e)}")

    db.commit()
    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }


# ============================================
# Entry point
# ============================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=True,
    )
