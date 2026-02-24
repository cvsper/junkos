"""
Temporary migration endpoint - DELETE AFTER USE
Fixes database schema on production
"""
from flask import Blueprint, jsonify
import os

migration_bp = Blueprint('migration', __name__)

@migration_bp.route('/api/migrate-schema-emergency', methods=['POST'])
def migrate_schema():
    """
    ONE-TIME EMERGENCY MIGRATION
    Adds apple_id column and makes user columns nullable
    
    DELETE THIS ENDPOINT AFTER RUNNING ONCE
    """
    
    # Get database URL
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    if not DATABASE_URL:
        return jsonify({'error': 'DATABASE_URL not set'}), 500
    
    # Fix postgres:// -> postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        results = []
        
        # 1. Add apple_id column
        try:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='users' AND column_name='apple_id'
            """)
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN apple_id VARCHAR(255) UNIQUE")
                results.append("Added apple_id column")
            else:
                results.append("apple_id already exists")
        except Exception as e:
            results.append(f"apple_id error: {str(e)}")
        
        # 2-5. Make columns nullable
        for column in ['email', 'phone', 'name', 'password_hash']:
            try:
                cursor.execute(f"ALTER TABLE users ALTER COLUMN {column} DROP NOT NULL")
                results.append(f"Made {column} nullable")
            except Exception as e:
                results.append(f"{column}: {str(e)}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Schema migration complete',
            'results': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

