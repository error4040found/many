"""
Database Configuration & Connection Manager
Supports MySQL with connection pooling
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Database configuration from .env
DB_TYPE = os.getenv("DB_TYPE", "sqlite")
MYSQL_HOST = os.getenv("MYSQL_HOST", "45.113.224.7")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "fundsill_babu")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Babu@7474")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "fundsill_gmail_automation")

# Pool configuration
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
DB_ECHO = os.getenv("DB_ECHO", "false").lower() == "true"

# App configuration
SECRET_KEY = os.getenv("SECRET_KEY", "manychat-dashboard-secret-key-change-in-production-2026")
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# Google Sheets fallback
GOOGLE_APPS_SCRIPT_URL = os.getenv("GOOGLE_APPS_SCRIPT_URL", "")
GOOGLE_SPREADSHEET_NAME = os.getenv("GOOGLE_SPREADSHEET_NAME", "manychart")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "page_ids")

# Email alert
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENTS = [e.strip() for e in os.getenv("EMAIL_RECIPIENTS", "").split(",") if e.strip()]


def get_database_url() -> str:
    """Build database URL based on DB_TYPE"""
    if DB_TYPE == "mysql":
        # URL-encode the password for special characters
        from urllib.parse import quote_plus
        encoded_password = quote_plus(MYSQL_PASSWORD)
        return f"mysql+pymysql://{MYSQL_USER}:{encoded_password}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
    else:
        # Railway has persistent disk — SQLite works fine
        db_path = os.getenv("SQLITE_DB_PATH", os.path.join(os.path.dirname(__file__), "manychat_dashboard.db"))
        return f"sqlite:///{db_path}"


DATABASE_URL = get_database_url()

# Create engine with connection pooling
if DB_TYPE == "mysql":
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_timeout=DB_POOL_TIMEOUT,
        pool_recycle=DB_POOL_RECYCLE,
        pool_pre_ping=True,  # Test connections before use
        echo=DB_ECHO,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=DB_ECHO,
        connect_args={"check_same_thread": False},
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency: yields a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables"""
    Base.metadata.create_all(bind=engine)
    print(f"✅ Database initialized ({DB_TYPE}: {MYSQL_HOST if DB_TYPE == 'mysql' else 'local'})")
