"""
Seed database with existing page_ids.json data
Run this once to populate the database with initial data
"""

import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, init_db
from models import PageID
from auth import create_default_users


def seed_page_ids():
    """Import page_ids.json into the database"""
    # Path to page_ids.json in parent directory
    page_ids_file = os.path.join(os.path.dirname(__file__), "..", "page_ids.json")
    
    if not os.path.exists(page_ids_file):
        print(f"❌ page_ids.json not found at: {page_ids_file}")
        return 0

    with open(page_ids_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    pages = data.get("pages", [])
    if not pages:
        print("❌ No pages found in page_ids.json")
        return 0

    db = SessionLocal()
    try:
        imported = 0
        skipped = 0
        
        for page in pages:
            page_id = page.get("id", "")
            name = page.get("name", "")
            user = page.get("user", "")
            tl = page.get("tl", "")
            account_name = page.get("account_name", "")

            if not page_id:
                continue

            # Check if already exists
            existing = db.query(PageID).filter(PageID.page_id == page_id).first()
            if existing:
                skipped += 1
                continue

            new_page = PageID(
                page_id=page_id,
                name=name,
                user=user,
                tl=tl,
                account_name=account_name,
                is_active=True,
            )
            db.add(new_page)
            imported += 1

        db.commit()
        print(f"✅ Imported {imported} pages, skipped {skipped} (already exist)")
        return imported
    except Exception as e:
        db.rollback()
        print(f"❌ Error importing pages: {e}")
        raise
    finally:
        db.close()


def seed_users():
    """Create default dashboard users"""
    db = SessionLocal()
    try:
        create_default_users(db)
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("🌱 ManyChat Dashboard - Database Seeder")
    print("=" * 60)
    
    # Initialize tables
    print("\n📦 Creating database tables...")
    init_db()
    
    # Seed users
    print("\n👤 Creating default users...")
    seed_users()
    
    # Seed page IDs
    print("\n📄 Importing page IDs from page_ids.json...")
    seed_page_ids()
    
    print("\n✅ Database seeding complete!")
    print("\n📋 Default Login Credentials:")
    print("   admin    / admin@123    (Administrator)")
    print("   babu     / babu@123     (Editor)")
    print("   subhajit / subhajit@123 (Editor)")
