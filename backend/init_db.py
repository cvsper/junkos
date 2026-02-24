#!/usr/bin/env python3
"""
Database Initialization Script for Umuve Backend

Creates all required tables using SQLAlchemy models.
Idempotent - safe to run multiple times.

Usage:
    python init_db.py
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize the database by creating all tables."""
    try:
        # Import Flask app and models
        logger.info("Importing Flask and models...")
        from flask import Flask
        from app_config import Config
        from models import db

        logger.info("Creating Flask app...")
        # Create minimal Flask app
        app = Flask(__name__)
        app.config.from_object(Config)

        # Configure database URL
        database_url = os.environ.get("DATABASE_URL", "")
        if database_url:
            # Fix postgres:// to postgresql:// for SQLAlchemy 2.x
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            app.config["SQLALCHEMY_DATABASE_URI"] = database_url
            logger.info(f"Using PostgreSQL database")
        else:
            # Fallback to SQLite for local development
            app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///umuve.db"
            logger.info(f"Using SQLite database: umuve.db")

        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

        # Initialize SQLAlchemy with app
        db.init_app(app)

        # Create all tables within app context
        with app.app_context():
            logger.info("Creating database tables...")
            db.create_all()
            logger.info("✓ All tables created successfully!")

            # List all created tables
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            logger.info(f"✓ Total tables: {len(tables)}")
            logger.info("Tables created:")
            for table in sorted(tables):
                logger.info(f"  - {table}")

        return True

    except ImportError as e:
        logger.error(f"✗ Import error: {str(e)}")
        logger.error("Make sure all dependencies are installed:")
        logger.error("  pip install -r requirements.txt")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        logger.error(f"✗ Database initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Umuve Database Initialization")
    logger.info("=" * 60)

    success = init_database()

    if success:
        logger.info("=" * 60)
        logger.info("Database initialization completed successfully!")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("=" * 60)
        logger.error("Database initialization failed!")
        logger.error("=" * 60)
        sys.exit(1)
