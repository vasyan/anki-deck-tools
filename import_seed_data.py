#!/usr/bin/env python
"""
Import seed data from JSON file into the database.
This script reads the seed data and recreates all records with proper relationships.
"""

import json
import base64
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

# Import models
from models.database import (
    Base, 
    LearningContent, 
    ContentFragment, 
    FragmentAsset, 
    AnkiCard,
    VectorEmbedding,
    Ranking
)

def parse_datetime(date_string: str | None) -> datetime | None:
    """Parse ISO format datetime string"""
    if date_string:
        return datetime.fromisoformat(date_string)
    return None

def import_seed_data(session: Session, seed_file: Path, clear_existing: bool = False):
    """Import seed data from JSON file"""
    
    # Load seed data
    with open(seed_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    metadata = data.get("metadata", {})
    learning_contents = data.get("learning_contents", [])
    
    print(f"Loading seed data from: {seed_file}")
    print(f"Extraction date: {metadata.get('extraction_date')}")
    print(f"Records to import: {metadata.get('record_count')}")
    
    if clear_existing:
        print("Clearing existing data...")
        # Delete in reverse order of dependencies
        session.query(Ranking).delete()
        session.query(VectorEmbedding).delete()
        session.query(FragmentAsset).delete()
        session.query(ContentFragment).delete()
        session.query(AnkiCard).delete()
        session.query(LearningContent).delete()
        session.commit()
        print("Existing data cleared.")
    
    # Track ID mappings for foreign key relationships
    lc_id_map = {}  # old_id -> new_id
    fragment_id_map = {}
    asset_id_map = {}
    card_id_map = {}
    
    # Import LearningContent
    for lc_data in learning_contents:
        lc = LearningContent(
            title=lc_data["title"],
            content_type=lc_data["content_type"],
            language=lc_data["language"],
            native_text=lc_data["native_text"],
            translation=lc_data["translation"],
            ipa=lc_data["ipa"],
            difficulty_level=lc_data["difficulty_level"],
            tags=lc_data["tags"],
            content_metadata=lc_data["content_metadata"],
            created_at=parse_datetime(lc_data["created_at"]),
            updated_at=parse_datetime(lc_data["updated_at"]),
            last_review_at=parse_datetime(lc_data["last_review_at"])
        )
        session.add(lc)
        session.flush()  # Get the new ID
        lc_id_map[lc_data["id"]] = lc.id
        
        # Import related ContentFragments
        for fragment_data in lc_data.get("fragments", []):
            fragment = ContentFragment(
                native_text=fragment_data["native_text"],
                body_text=fragment_data["body_text"],
                ipa=fragment_data["ipa"],
                extra=fragment_data["extra"],
                fragment_type=fragment_data["fragment_type"],
                fragment_metadata=fragment_data["fragment_metadata"],
                created_at=parse_datetime(fragment_data["created_at"]),
                updated_at=parse_datetime(fragment_data["updated_at"]),
                learning_content_id=lc.id
            )
            session.add(fragment)
            session.flush()
            fragment_id_map[fragment_data["id"]] = fragment.id
            
            # Import related FragmentAssets
            for asset_data in fragment_data.get("assets", []):
                # Decode base64 binary data if present
                binary_data = None
                if asset_data.get("asset_data"):
                    binary_data = base64.b64decode(asset_data["asset_data"])
                
                asset = FragmentAsset(
                    fragment_id=fragment.id,
                    asset_type=asset_data["asset_type"],
                    asset_data=binary_data,
                    asset_metadata=asset_data["asset_metadata"],
                    created_at=parse_datetime(asset_data["created_at"]),
                    created_by=asset_data["created_by"]
                )
                session.add(asset)
                session.flush()
                asset_id_map[asset_data["id"]] = asset.id
                
                # Import related Rankings
                for ranking_data in asset_data.get("rankings", []):
                    ranking = Ranking(
                        fragment_id=fragment.id,
                        asset_id=asset.id,
                        rank_score=ranking_data["rank_score"],
                        assessed_by=ranking_data["assessed_by"],
                        assessment_notes=ranking_data["assessment_notes"],
                        created_at=parse_datetime(ranking_data["created_at"]),
                        updated_at=parse_datetime(ranking_data["updated_at"])
                    )
                    session.add(ranking)
        
        # Import related AnkiCards
        for card_data in lc_data.get("anki_cards", []):
            card = AnkiCard(
                anki_note_id=card_data["anki_note_id"],
                deck_name=card_data["deck_name"],
                tags=card_data["tags"],
                created_at=parse_datetime(card_data["created_at"]),
                updated_at=parse_datetime(card_data["updated_at"]),
                learning_content_id=lc.id,
                export_hash=card_data["export_hash"]
            )
            session.add(card)
            session.flush()
            card_id_map[card_data["id"]] = card.id
            
            # Import related VectorEmbeddings
            for embedding_data in card_data.get("embeddings", []):
                embedding = VectorEmbedding(
                    card_id=card.id,
                    embedding_type=embedding_data["embedding_type"],
                    vector_data=embedding_data["vector_data"],
                    vector_dimension=embedding_data["vector_dimension"],
                    created_at=parse_datetime(embedding_data["created_at"])
                )
                session.add(embedding)
    
    # Commit all changes
    session.commit()
    
    print(f"✓ Imported {len(lc_id_map)} LearningContent records")
    print(f"✓ Imported {len(fragment_id_map)} ContentFragment records")
    print(f"✓ Imported {len(asset_id_map)} FragmentAsset records")
    print(f"✓ Imported {len(card_id_map)} AnkiCard records")
    print("Import completed successfully!")

def main():
    """Main import function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Import seed data into the database")
    parser.add_argument(
        "--input", 
        type=str, 
        default="seed_data.json",
        help="Path to the seed data JSON file"
    )
    parser.add_argument(
        "--database", 
        type=str, 
        default="sqlite:///anki_vector_seed.db",
        help="Database URL to import into"
    )
    parser.add_argument(
        "--clear", 
        action="store_true",
        help="Clear existing data before importing"
    )
    
    args = parser.parse_args()
    
    # Setup database connection
    engine = create_engine(args.database)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create tables if they don't exist
    print(f"Setting up database: {args.database}")
    Base.metadata.create_all(bind=engine)
    
    # Import data
    with SessionLocal() as session:
        seed_file = Path(args.input)
        if not seed_file.exists():
            print(f"Error: Seed file not found: {seed_file}")
            exit(1)
        
        import_seed_data(session, seed_file, clear_existing=args.clear)

if __name__ == "__main__":
    main()