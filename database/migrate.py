#!/usr/bin/env python3
"""
JunkOS Database Migration Tool
================================
Run database migrations with proper error handling and rollback support.

Usage:
    python migrate.py                  # Run all pending migrations
    python migrate.py --create <name>  # Create a new migration file
    python migrate.py --status         # Show migration status
    python migrate.py --to <version>   # Migrate to specific version
"""

import os
import sys
import argparse
import psycopg2
from psycopg2 import sql
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional
import re

# Configuration
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres@localhost/junkos")


class MigrationManager:
    """Handles database migrations with transaction support"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(self.database_url)
            self.cursor = self.conn.cursor()
            print(f"✓ Connected to database")
        except psycopg2.Error as e:
            print(f"✗ Database connection failed: {e}")
            sys.exit(1)
    
    def close(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def ensure_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    id SERIAL PRIMARY KEY,
                    version VARCHAR(255) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    checksum VARCHAR(64),
                    execution_time_ms INTEGER
                );
                
                CREATE INDEX IF NOT EXISTS idx_schema_migrations_version 
                ON schema_migrations(version);
            """)
            self.conn.commit()
            print("✓ Migration tracking table ready")
        except psycopg2.Error as e:
            print(f"✗ Failed to create migrations table: {e}")
            self.conn.rollback()
            sys.exit(1)
    
    def get_applied_migrations(self) -> List[str]:
        """Get list of already applied migration versions"""
        try:
            self.cursor.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
            return [row[0] for row in self.cursor.fetchall()]
        except psycopg2.Error as e:
            print(f"✗ Failed to fetch applied migrations: {e}")
            return []
    
    def get_pending_migrations(self) -> List[Tuple[str, Path]]:
        """Get list of pending migrations from filesystem"""
        if not MIGRATIONS_DIR.exists():
            MIGRATIONS_DIR.mkdir(parents=True)
            print(f"✓ Created migrations directory: {MIGRATIONS_DIR}")
            return []
        
        applied = set(self.get_applied_migrations())
        all_migrations = []
        
        # Find all .sql files in migrations directory
        for file_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            match = re.match(r"^(\d{14})_(.+)\.sql$", file_path.name)
            if match:
                version = match.group(1)
                if version not in applied:
                    all_migrations.append((version, file_path))
        
        return all_migrations
    
    def calculate_checksum(self, content: str) -> str:
        """Calculate SHA-256 checksum of migration content"""
        import hashlib
        return hashlib.sha256(content.encode()).hexdigest()
    
    def apply_migration(self, version: str, file_path: Path) -> bool:
        """Apply a single migration file"""
        try:
            print(f"\n→ Applying migration {version}: {file_path.name}")
            
            # Read migration file
            with open(file_path, 'r') as f:
                migration_sql = f.read()
            
            # Calculate checksum
            checksum = self.calculate_checksum(migration_sql)
            
            # Start timing
            start_time = datetime.now()
            
            # Execute migration in transaction
            try:
                self.cursor.execute(migration_sql)
                
                # Record migration
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                self.cursor.execute("""
                    INSERT INTO schema_migrations (version, name, checksum, execution_time_ms)
                    VALUES (%s, %s, %s, %s)
                """, (version, file_path.stem, checksum, execution_time))
                
                self.conn.commit()
                
                print(f"✓ Migration {version} applied successfully ({execution_time}ms)")
                return True
                
            except psycopg2.Error as e:
                self.conn.rollback()
                print(f"✗ Migration {version} failed: {e}")
                print(f"  Rolling back transaction...")
                return False
                
        except FileNotFoundError:
            print(f"✗ Migration file not found: {file_path}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error applying migration: {e}")
            return False
    
    def run_migrations(self, target_version: Optional[str] = None):
        """Run all pending migrations"""
        pending = self.get_pending_migrations()
        
        if not pending:
            print("\n✓ No pending migrations")
            return True
        
        print(f"\n→ Found {len(pending)} pending migration(s)")
        
        for version, file_path in pending:
            if target_version and version > target_version:
                print(f"  Skipping {version} (beyond target version {target_version})")
                continue
                
            if not self.apply_migration(version, file_path):
                print(f"\n✗ Migration failed. Stopping.")
                return False
        
        print(f"\n✓ All migrations completed successfully")
        return True
    
    def show_status(self):
        """Display migration status"""
        applied = self.get_applied_migrations()
        pending = self.get_pending_migrations()
        
        print(f"\n{'='*70}")
        print(f"Database Migration Status")
        print(f"{'='*70}\n")
        
        print(f"Database: {self.database_url.split('@')[-1]}")
        print(f"Applied migrations: {len(applied)}")
        print(f"Pending migrations: {len(pending)}\n")
        
        if applied:
            print("Applied Migrations:")
            print("-" * 70)
            self.cursor.execute("""
                SELECT version, name, applied_at, execution_time_ms
                FROM schema_migrations
                ORDER BY version
            """)
            for row in self.cursor.fetchall():
                version, name, applied_at, exec_time = row
                print(f"  ✓ {version} - {name}")
                print(f"    Applied: {applied_at.strftime('%Y-%m-%d %H:%M:%S')} ({exec_time}ms)")
        
        if pending:
            print("\nPending Migrations:")
            print("-" * 70)
            for version, file_path in pending:
                print(f"  ○ {version} - {file_path.name}")
        
        print(f"\n{'='*70}\n")
    
    def create_migration(self, name: str):
        """Create a new migration file"""
        # Generate version timestamp
        version = datetime.now().strftime("%Y%m%d%H%M%S")
        
        # Sanitize name
        clean_name = re.sub(r'[^a-z0-9_]', '_', name.lower())
        
        # Create filename
        filename = f"{version}_{clean_name}.sql"
        file_path = MIGRATIONS_DIR / filename
        
        # Ensure migrations directory exists
        MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create migration template
        template = f"""-- Migration: {name}
-- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- ============================================================================

BEGIN;

-- ============================================================================
-- UP MIGRATION
-- ============================================================================

-- TODO: Add your migration SQL here


-- ============================================================================
-- ROLLBACK SQL (for rollback.py)
-- ============================================================================
-- To rollback this migration, add the reverse operations below as comments
-- Example:
-- ROLLBACK: DROP TABLE IF EXISTS new_table;
-- ROLLBACK: ALTER TABLE users DROP COLUMN new_column;

COMMIT;
"""
        
        # Write template
        with open(file_path, 'w') as f:
            f.write(template)
        
        print(f"\n✓ Created new migration: {filename}")
        print(f"  Location: {file_path}")
        print(f"\n→ Edit the file to add your migration SQL")
        print(f"→ Run 'python migrate.py' to apply it")


def main():
    parser = argparse.ArgumentParser(
        description="JunkOS Database Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--create',
        metavar='NAME',
        help='Create a new migration file'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show migration status'
    )
    
    parser.add_argument(
        '--to',
        metavar='VERSION',
        help='Migrate to specific version'
    )
    
    parser.add_argument(
        '--db',
        metavar='URL',
        help='Database URL (overrides DATABASE_URL env var)'
    )
    
    args = parser.parse_args()
    
    # Override database URL if provided
    db_url = args.db if args.db else DATABASE_URL
    
    # Create migration manager
    manager = MigrationManager(db_url)
    
    # Handle create command without database connection
    if args.create:
        manager.create_migration(args.create)
        return
    
    # Connect to database for other operations
    manager.connect()
    
    try:
        manager.ensure_migrations_table()
        
        if args.status:
            manager.show_status()
        else:
            # Run migrations
            manager.run_migrations(target_version=args.to)
    
    finally:
        manager.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)
