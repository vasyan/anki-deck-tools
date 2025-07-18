#!/usr/bin/env python3
"""
Migration script to transform ExampleAudio from one-to-many to many-to-many relationship with AnkiCard.

This script:
1. Creates the new junction table structure
2. Migrates existing data from old structure to new structure
3. Provides rollback capability
"""

import sqlite3
from datetime import datetime
from database.manager import DatabaseManager
from models.database import Base, CardExampleAudioAssociation, ExampleAudio, AnkiCard
from sqlalchemy import text

def migrate_to_many_to_many():
    """
    Migrate existing one-to-many relationship to many-to-many relationship.
    """
    db_manager = DatabaseManager()
    
    print("Starting migration to many-to-many relationship...")
    
    # Create all tables (including the new junction table)
    with db_manager.engine.connect() as conn:
        Base.metadata.create_all(db_manager.engine)
        print("✓ Created new junction table: card_example_audio_association")
    
    # Check if old structure exists
    with db_manager.get_session() as session:
        # Check if card_id column exists in example_audio table
        try:
            result = session.execute(text("PRAGMA table_info(example_audio)"))
            columns = [row[1] for row in result.fetchall()]
            has_card_id = 'card_id' in columns
            
            if not has_card_id:
                print("✓ Migration already completed - no card_id column found in example_audio table")
                return
                
            print(f"✓ Found old structure with card_id column")
            
            # Get all existing example audio records with their card associations
            result = session.execute(text("""
                SELECT id, card_id, order_index, created_at
                FROM example_audio 
                WHERE card_id IS NOT NULL
                ORDER BY card_id, order_index
            """))
            
            old_associations = result.fetchall()
            print(f"✓ Found {len(old_associations)} existing audio-card associations")
            
            # Create new association records
            associations_created = 0
            for audio_id, card_id, order_index, created_at in old_associations:
                # Insert into junction table
                session.execute(text("""
                    INSERT INTO card_example_audio_association 
                    (card_id, example_audio_id, order_index, created_at)
                    VALUES (:card_id, :audio_id, :order_index, :created_at)
                """), {
                    'card_id': card_id,
                    'audio_id': audio_id,
                    'order_index': order_index or 0,
                    'created_at': created_at or datetime.utcnow()
                })
                associations_created += 1
            
            session.commit()
            print(f"✓ Created {associations_created} new association records")
            
            # Create backup of old structure
            backup_table_name = f"example_audio_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            session.execute(text(f"""
                CREATE TABLE {backup_table_name} AS 
                SELECT * FROM example_audio
            """))
            print(f"✓ Created backup table: {backup_table_name}")
            
            # Remove old columns from example_audio table
            # SQLite doesn't support DROP COLUMN, so we need to recreate the table
            session.execute(text("""
                CREATE TABLE example_audio_new (
                    id INTEGER PRIMARY KEY,
                    audio_blob BLOB NOT NULL,
                    example_text TEXT NOT NULL,
                    tts_model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Copy data without card_id and order_index
            session.execute(text("""
                INSERT INTO example_audio_new (id, audio_blob, example_text, tts_model, created_at)
                SELECT id, audio_blob, example_text, tts_model, created_at
                FROM example_audio
            """))
            
            # Replace old table with new one
            session.execute(text("DROP TABLE example_audio"))
            session.execute(text("ALTER TABLE example_audio_new RENAME TO example_audio"))
            
            session.commit()
            print("✓ Removed old card_id and order_index columns from example_audio table")
            
        except Exception as e:
            session.rollback()
            raise Exception(f"Migration failed: {e}")
    
    print("✅ Migration completed successfully!")
    print("\nNext steps:")
    print("1. Update your application code to use the new many-to-many relationship")
    print("2. Test the application thoroughly")
    print("3. If everything works, you can drop the backup table")

def rollback_migration():
    """
    Rollback the migration by restoring the old structure.
    """
    db_manager = DatabaseManager()
    
    with db_manager.get_session() as session:
        # Find the most recent backup table
        result = session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE 'example_audio_backup_%'
            ORDER BY name DESC
            LIMIT 1
        """))
        
        backup_table = result.fetchone()
        if not backup_table:
            print("❌ No backup table found - cannot rollback")
            return
            
        backup_table_name = backup_table[0]
        print(f"Found backup table: {backup_table_name}")
        
        # Restore from backup
        session.execute(text("DROP TABLE IF EXISTS example_audio"))
        session.execute(text(f"ALTER TABLE {backup_table_name} RENAME TO example_audio"))
        session.execute(text("DROP TABLE IF EXISTS card_example_audio_association"))
        
        session.commit()
        print("✅ Migration rolled back successfully")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback_migration()
    else:
        migrate_to_many_to_many() 
