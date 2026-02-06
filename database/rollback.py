#!/usr/bin/env python3
"""
JunkOS Database Rollback Tool
==============================
Rollback the last applied migration or rollback to a specific version.

Usage:
    python rollback.py              # Rollback last migration
    python rollback.py --to <version>  # Rollback to specific version
    python rollback.py --list       # List rollback history
"""

import os
import sys
import argparse
import psycopg2
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import re

# Configuration
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres@localhost/junkos")


class RollbackManager:
    """Handles database migration rollbacks"""
    
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
    
    def get_last_migration(self) -> Optional[tuple]:
        """Get the most recently applied migration"""
        try:
            self.cursor.execute("""
                SELECT version, name, applied_at
                FROM schema_migrations
                ORDER BY version DESC
                LIMIT 1
            """)
            result = self.cursor.fetchone()
            return result
        except psycopg2.Error as e:
            print(f"✗ Failed to fetch last migration: {e}")
            return None
    
    def get_applied_migrations(self) -> List[tuple]:
        """Get all applied migrations"""
        try:
            self.cursor.execute("""
                SELECT version, name, applied_at
                FROM schema_migrations
                ORDER BY version DESC
            """)
            return self.cursor.fetchall()
        except psycopg2.Error as e:
            print(f"✗ Failed to fetch migrations: {e}")
            return []
    
    def extract_rollback_sql(self, file_path: Path) -> Optional[str]:
        """Extract rollback SQL from migration file comments"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Look for ROLLBACK: comments
            rollback_lines = []
            for line in content.split('\n'):
                match = re.match(r'^\s*--\s*ROLLBACK:\s*(.+)$', line, re.IGNORECASE)
                if match:
                    rollback_lines.append(match.group(1).strip())
            
            if rollback_lines:
                return '\n'.join(rollback_lines)
            else:
                return None
                
        except FileNotFoundError:
            print(f"✗ Migration file not found: {file_path}")
            return None
        except Exception as e:
            print(f"✗ Error reading migration file: {e}")
            return None
    
    def rollback_migration(self, version: str, name: str, auto_rollback: bool = False) -> bool:
        """Rollback a specific migration"""
        print(f"\n→ Rolling back migration {version}: {name}")
        
        # Find migration file
        migration_file = MIGRATIONS_DIR / f"{version}_{name}.sql"
        if not migration_file.exists():
            # Try to find by version alone (name might have changed)
            matches = list(MIGRATIONS_DIR.glob(f"{version}_*.sql"))
            if matches:
                migration_file = matches[0]
            else:
                print(f"✗ Migration file not found: {migration_file}")
                return False
        
        # Extract rollback SQL
        rollback_sql = self.extract_rollback_sql(migration_file)
        
        if not rollback_sql:
            print(f"⚠ No rollback SQL found in migration file")
            if not auto_rollback:
                print(f"  Manual rollback required!")
                print(f"  Migration file: {migration_file}")
                
                response = input(f"\n  Remove this migration from history anyway? (yes/no): ")
                if response.lower() != 'yes':
                    print(f"✗ Rollback cancelled")
                    return False
        else:
            print(f"  Found rollback SQL ({len(rollback_sql.split(';'))} statement(s))")
        
        # Execute rollback
        try:
            if rollback_sql:
                print(f"  Executing rollback SQL...")
                self.cursor.execute(rollback_sql)
            
            # Remove from migrations table
            self.cursor.execute("""
                DELETE FROM schema_migrations
                WHERE version = %s
            """, (version,))
            
            self.conn.commit()
            print(f"✓ Migration {version} rolled back successfully")
            return True
            
        except psycopg2.Error as e:
            self.conn.rollback()
            print(f"✗ Rollback failed: {e}")
            print(f"  Transaction rolled back")
            return False
    
    def rollback_last(self):
        """Rollback the most recent migration"""
        last = self.get_last_migration()
        
        if not last:
            print("\n✓ No migrations to rollback")
            return True
        
        version, name, applied_at = last
        
        print(f"\n{'='*70}")
        print(f"Last Migration")
        print(f"{'='*70}")
        print(f"  Version: {version}")
        print(f"  Name: {name}")
        print(f"  Applied: {applied_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        
        response = input(f"Rollback this migration? (yes/no): ")
        if response.lower() != 'yes':
            print(f"✗ Rollback cancelled")
            return False
        
        return self.rollback_migration(version, name)
    
    def rollback_to_version(self, target_version: str):
        """Rollback all migrations after target version"""
        applied = self.get_applied_migrations()
        
        if not applied:
            print("\n✓ No migrations to rollback")
            return True
        
        # Find migrations to rollback
        to_rollback = [m for m in applied if m[0] > target_version]
        
        if not to_rollback:
            print(f"\n✓ Already at or before version {target_version}")
            return True
        
        print(f"\n→ Will rollback {len(to_rollback)} migration(s) to reach version {target_version}")
        print(f"\nMigrations to rollback:")
        for version, name, applied_at in to_rollback:
            print(f"  • {version} - {name}")
        
        response = input(f"\nProceed with rollback? (yes/no): ")
        if response.lower() != 'yes':
            print(f"✗ Rollback cancelled")
            return False
        
        # Rollback in reverse order
        for version, name, _ in to_rollback:
            if not self.rollback_migration(version, name, auto_rollback=True):
                print(f"\n✗ Rollback failed. Some migrations may have been rolled back.")
                return False
        
        print(f"\n✓ Successfully rolled back to version {target_version}")
        return True
    
    def list_rollback_history(self):
        """Show rollback-capable migrations"""
        applied = self.get_applied_migrations()
        
        print(f"\n{'='*70}")
        print(f"Applied Migrations (rollback order)")
        print(f"{'='*70}\n")
        
        if not applied:
            print("No migrations applied yet\n")
            return
        
        for version, name, applied_at in applied:
            migration_file = None
            for file_path in MIGRATIONS_DIR.glob(f"{version}_*.sql"):
                migration_file = file_path
                break
            
            has_rollback = False
            if migration_file:
                rollback_sql = self.extract_rollback_sql(migration_file)
                has_rollback = bool(rollback_sql)
            
            rollback_status = "✓ Has rollback" if has_rollback else "⚠ Manual rollback"
            
            print(f"  {version} - {name}")
            print(f"    Applied: {applied_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"    {rollback_status}")
            print()
        
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(
        description="JunkOS Database Rollback Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--to',
        metavar='VERSION',
        help='Rollback to specific version (all migrations after will be rolled back)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List rollback history'
    )
    
    parser.add_argument(
        '--db',
        metavar='URL',
        help='Database URL (overrides DATABASE_URL env var)'
    )
    
    args = parser.parse_args()
    
    # Override database URL if provided
    db_url = args.db if args.db else DATABASE_URL
    
    # Create rollback manager
    manager = RollbackManager(db_url)
    manager.connect()
    
    try:
        if args.list:
            manager.list_rollback_history()
        elif args.to:
            manager.rollback_to_version(args.to)
        else:
            manager.rollback_last()
    
    finally:
        manager.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Rollback cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)
